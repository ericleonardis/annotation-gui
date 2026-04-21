"""Macro-behavior auto-labeler driven by track/stac qpos.

Reads a 74-column qpos CSV (q0..q73) and produces a list of per-frame-grouped
segment dicts, labeled with one of the 5 macro behaviors:

    Immobile, Rear, Turn, Walk, Groom

Direction inference (Left/Right/Straight) is handled by a separate pipeline
in `auto_direction.py`. This module does NOT emit direction information.

Column assumptions (inferred empirically — see docs/auto_labeling.md):

    q0, q1     — root planar position (x, y)
    q2         — root height (z)
    q3..q6     — root orientation quaternion (w, x, y, z)
    q7..q40    — forelimb + upper-body joints (forelimb activity proxy)
    q41..q73   — hindlimb + tail joints (hindlimb activity proxy)

Decision rules (first match wins, per frame):

    1. elevated          -> Rear     (root z is high or rising)
    2. stationary_rot    -> Turn     (not translating, body rotating)
    3. forelimbs + hind-limbs-planted + still planar -> Groom
    4. v_xy > walk_xy    -> Walk     (purely planar motion)
    5. otherwise         -> Immobile

Where:
    elevated       = z_abs > rear_z_abs OR z_rel > rear_z_delta
    stationary_rot = v_xy < walk_xy AND |yaw_rate| > orient_yaw
    (Groom fires only when not elevated — rule ordering handles it)

After grouping into segments, a bridging pass merges triples of the form
A -> B -> A where duration(B) < bridge_threshold (default 0.5 s).
"""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent

DEFAULT_CONFIG: Dict[str, float] = {
    "window": 15,
    "fps": 30.0,
    "min_segment_duration": 0.25,
    "bridge_threshold": 0.5,
    # Any segment shorter than this (seconds) is absorbed into whichever
    # neighbor is longer, regardless of label. Stricter than bridging
    # because it merges even when neighbors disagree.
    "short_absorb_threshold": 0.5,
    "still_xy": 0.003,
    # Walking requires noticeable planar velocity. Raised further (was
    # 0.003) so that clear, sustained translation is needed — anything
    # below becomes Turn (if rotating) or Immobile (if not).
    "walk_xy": 0.005,
    # Immobile is the default fall-through — but a stricter standard means
    # a frame-by-frame lull is not enough; the still spell must last a
    # minimum duration to qualify. Shorter Immobile segments are absorbed
    # into whichever neighbor is longer.
    "immobile_min_duration": 1.0,
    "rear_z_abs": 0.07,
    "rear_z_delta": 0.03,
    "orient_yaw": 0.015,
    "groom_limb": 0.0004,
    "still_hindlimb": 0.0005,
    "forelimb_first": 7,
    "forelimb_last": 40,
    "hindlimb_first": 41,
    "hindlimb_last": 73,
    # Direction threshold lives here for convenience of the calibrator but is
    # consumed by auto_direction.py; keeping the key stable avoids splitting
    # config files. Raised to require a clearly committed yaw rate before a
    # frame is called Left or Right — slow drifting yaw stays Straight.
    "dir_yaw_thresh": 0.03,
    # Minimum direction-segment duration (seconds). Short Left/Right spans
    # get absorbed into the surrounding Straight unless they're decisive.
    "dir_min_duration": 1.5,
}


def load_config() -> Dict[str, float]:
    path = _HERE / "auto_label_config.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    return dict(DEFAULT_CONFIG)


def read_qpos(path: str) -> List[List[float]]:
    """Read a qpos CSV into a list-of-lists of floats (one row per frame)."""
    rows: List[List[float]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        _header = next(reader, None)
        for r in reader:
            if not r:
                continue
            try:
                rows.append([float(x) for x in r])
            except ValueError:
                continue
    return rows


def _quat_to_yaw(w: float, x: float, y: float, z: float) -> float:
    """Yaw (rotation about z) from a (w, x, y, z) quaternion."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def _unwrap(angles: Sequence[float]) -> List[float]:
    """Numpy-free angle unwrap in [-pi, pi]."""
    if not angles:
        return []
    out = [angles[0]]
    for a in angles[1:]:
        diff = a - out[-1]
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        out.append(out[-1] + diff)
    return out


def _window_rms(values: Sequence[float], start: int, end: int) -> float:
    """RMS of first-differences within [start, end)."""
    if end - start < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(start + 1, end):
        d = values[i] - values[i - 1]
        total += d * d
        count += 1
    if count == 0:
        return 0.0
    return math.sqrt(total / count)


def _window_variance(
    rows: Sequence[Sequence[float]],
    cols: Sequence[int],
    start: int,
    end: int,
) -> float:
    """Mean variance across a set of columns within [start, end)."""
    if end - start < 2 or not cols:
        return 0.0
    per_col_vars = []
    for c in cols:
        vals = [rows[i][c] for i in range(start, end)]
        m = sum(vals) / len(vals)
        v = sum((x - m) ** 2 for x in vals) / len(vals)
        per_col_vars.append(v)
    return sum(per_col_vars) / len(per_col_vars)


def compute_features(
    rows: List[List[float]], cfg: Optional[Dict[str, float]] = None
) -> List[Dict[str, float]]:
    """Compute per-frame features.

    Returns a list of dicts with keys:
        v_xy, v_z, z_abs, z_rel, yaw_rate, forelimb_var, hindlimb_var, yaw
    """
    if cfg is None:
        cfg = load_config()
    n = len(rows)
    if n == 0:
        return []

    window = int(cfg["window"])
    half = max(1, window // 2)
    n_cols = len(rows[0]) if rows else 0
    forelimb_cols = [
        c
        for c in range(int(cfg["forelimb_first"]), int(cfg["forelimb_last"]) + 1)
        if c < n_cols
    ]
    hindlimb_cols = [
        c
        for c in range(int(cfg["hindlimb_first"]), int(cfg["hindlimb_last"]) + 1)
        if c < n_cols
    ]

    z_median = sorted(r[2] for r in rows)[n // 2]

    raw_yaw = [_quat_to_yaw(r[3], r[4], r[5], r[6]) for r in rows]
    yaw_unwrapped = _unwrap(raw_yaw)

    feats: List[Dict[str, float]] = []
    for i in range(n):
        s = max(0, i - half)
        e = min(n, i + half + 1)

        v_xy = math.hypot(
            _window_rms([r[0] for r in rows], s, e),
            _window_rms([r[1] for r in rows], s, e),
        )
        v_z = _window_rms([r[2] for r in rows], s, e)
        z_abs = rows[i][2]
        z_rel = z_abs - z_median
        yaw_rate = _window_rms(yaw_unwrapped, s, e)
        forelimb_var = _window_variance(rows, forelimb_cols, s, e)
        hindlimb_var = _window_variance(rows, hindlimb_cols, s, e)
        feats.append(
            {
                "v_xy": v_xy,
                "v_z": v_z,
                "z_abs": z_abs,
                "z_rel": z_rel,
                "yaw_rate": yaw_rate,
                "forelimb_var": forelimb_var,
                "hindlimb_var": hindlimb_var,
                "yaw": yaw_unwrapped[i],
            }
        )
    return feats


def _classify_frame(f: Dict[str, float], cfg: Dict[str, float]) -> str:
    """Apply the 5-class decision rule to a single frame."""
    elevated = (
        f["z_abs"] > cfg["rear_z_abs"]
        or f["z_rel"] > cfg["rear_z_delta"]
    )
    low_planar = f["v_xy"] < cfg["walk_xy"]
    stationary_rot = low_planar and f["yaw_rate"] > cfg["orient_yaw"]
    forelimb_busy = f["forelimb_var"] > cfg["groom_limb"]
    hindlimb_quiet = f["hindlimb_var"] < cfg["still_hindlimb"]

    if elevated:
        return "Rear"
    if stationary_rot:
        return "Turn"
    if low_planar and forelimb_busy and hindlimb_quiet:
        return "Groom"
    if f["v_xy"] > cfg["walk_xy"]:
        return "Walk"
    return "Immobile"


def _group_segments(
    labels: List[str], cfg: Dict[str, float]
) -> List[Tuple[str, int, int]]:
    """Group contiguous same-label frames.

    Two cleanup passes:
      1. Flicker filter: segments shorter than `min_segment_duration` are
         merged into the previous segment.
      2. Bridging: a single pass that merges triples A -> B -> A where
         duration(B) < bridge_threshold.
    """
    if not labels:
        return []
    fps = float(cfg["fps"])
    min_dur = float(cfg["min_segment_duration"])
    bridge = float(cfg["bridge_threshold"])

    raw: List[Tuple[str, int, int]] = []
    cur = labels[0]
    cur_start = 0
    for i in range(1, len(labels)):
        if labels[i] != cur:
            raw.append((cur, cur_start, i))
            cur = labels[i]
            cur_start = i
    raw.append((cur, cur_start, len(labels)))

    # Pass 1: flicker filter
    merged: List[Tuple[str, int, int]] = []
    for lbl, s, e in raw:
        dur = (e - s) / fps
        if dur < min_dur and merged:
            pl, ps, _ = merged[-1]
            merged[-1] = (pl, ps, e)
        else:
            merged.append((lbl, s, e))

    # Coalesce adjacent same-label runs that the flicker pass may have created
    coalesced: List[Tuple[str, int, int]] = []
    for lbl, s, e in merged:
        if coalesced and coalesced[-1][0] == lbl and coalesced[-1][2] == s:
            pl, ps, _ = coalesced[-1]
            coalesced[-1] = (pl, ps, e)
        else:
            coalesced.append((lbl, s, e))

    # Pass 2: bridging — A, B, A with short B -> single A
    bridged: List[Tuple[str, int, int]] = []
    i = 0
    while i < len(coalesced):
        if (
            i + 2 < len(coalesced)
            and coalesced[i][0] == coalesced[i + 2][0]
            and (coalesced[i + 1][2] - coalesced[i + 1][1]) / fps < bridge
        ):
            a_lbl, a_s, _a_e = coalesced[i]
            _b = coalesced[i + 1]
            _, _, c_e = coalesced[i + 2]
            bridged.append((a_lbl, a_s, c_e))
            i += 3
        else:
            bridged.append(coalesced[i])
            i += 1

    # Final coalescing in case bridging made neighbors equal
    final: List[Tuple[str, int, int]] = []
    for lbl, s, e in bridged:
        if final and final[-1][0] == lbl and final[-1][2] == s:
            pl, ps, _ = final[-1]
            final[-1] = (pl, ps, e)
        else:
            final.append((lbl, s, e))

    # Pass 3: absorb short segments (regardless of label match) into their
    # longer neighbor. Repeats until no segment under the threshold remains
    # or only one segment is left.
    short_thresh = float(cfg.get("short_absorb_threshold", 0.5))
    while True:
        shortest_idx = -1
        shortest_dur = float("inf")
        for i, (_, s, e) in enumerate(final):
            d = (e - s) / fps
            if d < short_thresh and d < shortest_dur:
                shortest_dur = d
                shortest_idx = i
        if shortest_idx < 0 or len(final) <= 1:
            break

        i = shortest_idx
        _, s, e = final[i]
        left_len = (
            (final[i - 1][2] - final[i - 1][1]) if i > 0 else -1
        )
        right_len = (
            (final[i + 1][2] - final[i + 1][1])
            if i + 1 < len(final)
            else -1
        )

        if left_len < 0 and right_len < 0:
            break

        if right_len > left_len:
            lbl, rs, re_ = final[i + 1]
            final[i + 1] = (lbl, s, re_)
            final.pop(i)
        else:
            lbl, ls, _ = final[i - 1]
            final[i - 1] = (lbl, ls, e)
            final.pop(i)

        coalesced: List[Tuple[str, int, int]] = []
        for seg in final:
            if coalesced and coalesced[-1][0] == seg[0] and coalesced[-1][2] == seg[1]:
                lbl, ps, _ = coalesced[-1]
                coalesced[-1] = (lbl, ps, seg[2])
            else:
                coalesced.append(seg)
        final = coalesced

    # Pass 4: stricter Immobile. An Immobile segment shorter than
    # `immobile_min_duration` gets folded into its longer neighbor — the
    # user wants the animal to be actually still for at least that long
    # before we call it Immobile.
    immob_min = float(cfg.get("immobile_min_duration", 1.0))
    while True:
        shortest_idx = -1
        shortest_dur = float("inf")
        for i, (lbl, s, e) in enumerate(final):
            if lbl != "Immobile":
                continue
            d = (e - s) / fps
            if d < immob_min and d < shortest_dur:
                shortest_dur = d
                shortest_idx = i
        if shortest_idx < 0 or len(final) <= 1:
            break

        i = shortest_idx
        _, s, e = final[i]
        left_len = (final[i - 1][2] - final[i - 1][1]) if i > 0 else -1
        right_len = (
            (final[i + 1][2] - final[i + 1][1])
            if i + 1 < len(final)
            else -1
        )
        if left_len < 0 and right_len < 0:
            break

        if right_len > left_len:
            lbl, _rs, re_ = final[i + 1]
            final[i + 1] = (lbl, s, re_)
            final.pop(i)
        else:
            lbl, ls, _ = final[i - 1]
            final[i - 1] = (lbl, ls, e)
            final.pop(i)

        coalesced: List[Tuple[str, int, int]] = []
        for seg in final:
            if coalesced and coalesced[-1][0] == seg[0] and coalesced[-1][2] == seg[1]:
                lbl, ps, _ = coalesced[-1]
                coalesced[-1] = (lbl, ps, seg[2])
            else:
                coalesced.append(seg)
        final = coalesced

    return final


def auto_label_clip(
    qpos_path: str,
    cfg: Optional[Dict[str, float]] = None,
    stac_path: Optional[str] = None,
) -> List[Dict[str, object]]:
    """Label a single clip given its qpos CSV path.

    Track is the primary signal. If `stac_path` is provided, stac features
    are blended in with a smaller weight (0.3 by default) as a helper.

    Returns a list of dicts: {name, start_time, end_time, start_frame, end_frame}.
    Suitable for constructing BehaviorSegment in the GUI.
    """
    if cfg is None:
        cfg = load_config()
    rows = read_qpos(qpos_path)
    feats = compute_features(rows, cfg)
    if stac_path:
        stac_rows = read_qpos(stac_path)
        if stac_rows:
            stac_feats = compute_features(stac_rows, cfg)
            feats = _blend_features(feats, stac_feats, weight_primary=0.7)
    labels = [_classify_frame(f, cfg) for f in feats]
    groups = _group_segments(labels, cfg)
    fps = float(cfg["fps"])

    out: List[Dict[str, object]] = []
    for lbl, s, e in groups:
        out.append(
            {
                "name": lbl,
                "start_time": s / fps,
                "end_time": e / fps,
                "start_frame": s,
                "end_frame": e,
            }
        )
    return out


def resolve_qpos_path(clip_name: str, csvs_dir: str) -> Optional[str]:
    """Find the best qpos CSV for a clip. Prefers track over stac."""
    primary, _ = resolve_qpos_pair(clip_name, csvs_dir)
    return primary


def resolve_qpos_pair(
    clip_name: str, csvs_dir: str
) -> Tuple[Optional[str], Optional[str]]:
    """Return (track_path, stac_path), either may be None if not on disk.

    Track is the primary source for classification; stac is a helper used
    to blend features and stabilize noisy tracking.
    """
    stem = os.path.splitext(os.path.basename(clip_name))[0]
    track = os.path.join(csvs_dir, f"{stem}_track_qpos.csv")
    stac = os.path.join(csvs_dir, f"{stem}_stac_qpos.csv")
    track_p = track if os.path.isfile(track) else None
    stac_p = stac if os.path.isfile(stac) else None
    return track_p, stac_p


def _blend_features(
    primary: List[Dict[str, float]],
    secondary: List[Dict[str, float]],
    weight_primary: float = 0.7,
) -> List[Dict[str, float]]:
    """Per-frame weighted blend of scalar features.

    `yaw` is kept from the primary track (quaternion-derived angles should
    not be linearly blended). Everything else is linearly combined.
    """
    n = min(len(primary), len(secondary))
    out: List[Dict[str, float]] = []
    w_p = float(weight_primary)
    w_s = 1.0 - w_p
    for i in range(n):
        p = primary[i]
        s = secondary[i]
        blended: Dict[str, float] = {}
        for k, v in p.items():
            if k == "yaw":
                blended[k] = v
            elif k in s and isinstance(v, (int, float)):
                blended[k] = w_p * v + w_s * s[k]
            else:
                blended[k] = v
        out.append(blended)
    for i in range(n, len(primary)):
        out.append(primary[i])
    return out
