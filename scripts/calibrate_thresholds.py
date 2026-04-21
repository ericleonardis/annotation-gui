"""Calibrate auto-labeler + auto-directionality thresholds from labeled data.

Input: the two-track converted CSV (output of convert_labels.py) and the
directory of per-clip qpos CSVs. For each labeled frame, computes the
macro-behavior features from `auto_labeler` and the signed yaw-rate from
`auto_direction`, then picks thresholds from the per-class distributions.

Usage:
    python scripts/calibrate_thresholds.py \
        sample/"Kevin clips (542 - 842)_converted.csv" \
        sample/csvs \
        auto_label_config.json
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from auto_labeler import (  # noqa: E402
    DEFAULT_CONFIG,
    _quat_to_yaw,
    _unwrap,
    compute_features,
    read_qpos,
    resolve_qpos_path,
)
from auto_direction import _signed_yaw_rate  # noqa: E402


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f_idx = int(k)
    c = min(f_idx + 1, len(s) - 1)
    if f_idx == c:
        return s[f_idx]
    return s[f_idx] + (s[c] - s[f_idx]) * (k - f_idx)


def collect(
    labels_csv: Path, csvs_dir: Path
) -> Tuple[Dict[str, Dict[str, List[float]]], Dict[str, List[float]]]:
    """Group per-frame features by manual behavior label, and gather signed
    yaw-rate inside Left/Right direction spans vs outside.

    Returns:
        per_class: { behavior_label: { feature_name: [values...] } }
        yaw_buckets: { "dir_in": [...], "dir_out": [...] } signed yaw-rate
    """
    per_class: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    yaw_buckets: Dict[str, List[float]] = {"dir_in": [], "dir_out": []}

    with open(labels_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    behavior_by_video: Dict[str, List[Tuple[str, float, float]]] = defaultdict(list)
    direction_by_video: Dict[str, List[Tuple[str, float, float]]] = defaultdict(list)
    for r in rows:
        track = r.get("Track", "behavior")
        label = r.get("Label") or r.get("Behavior", "")
        ts = float(r["Start_Time"])
        te = float(r["End_Time"])
        if track == "behavior":
            behavior_by_video[r["Video"]].append((label, ts, te))
        elif track == "direction":
            direction_by_video[r["Video"]].append((label, ts, te))

    cfg = dict(DEFAULT_CONFIG)
    fps = float(cfg["fps"])
    window = int(cfg["window"])

    processed = 0
    videos = set(list(behavior_by_video.keys()) + list(direction_by_video.keys()))
    for video in videos:
        qpath = resolve_qpos_path(video, str(csvs_dir))
        if qpath is None:
            continue
        qrows = read_qpos(qpath)
        if not qrows:
            continue
        feats = compute_features(qrows, cfg)

        raw_yaw = [_quat_to_yaw(r[3], r[4], r[5], r[6]) for r in qrows]
        yaw_unwrapped = _unwrap(raw_yaw)
        signed_rate = _signed_yaw_rate(yaw_unwrapped, window)

        # Behavior-feature distributions
        for label, ts, te in behavior_by_video.get(video, []):
            fs = int(round(ts * fps))
            fe = min(len(feats), int(round(te * fps)))
            for idx in range(fs, fe):
                if 0 <= idx < len(feats):
                    f = feats[idx]
                    for name in (
                        "v_xy",
                        "v_z",
                        "z_abs",
                        "z_rel",
                        "yaw_rate",
                        "forelimb_var",
                        "hindlimb_var",
                    ):
                        per_class[label][name].append(f[name])

        # Direction-rate buckets
        dir_mask = [False] * len(signed_rate)
        for label, ts, te in direction_by_video.get(video, []):
            fs = int(round(ts * fps))
            fe = min(len(signed_rate), int(round(te * fps)))
            for idx in range(fs, fe):
                if 0 <= idx < len(dir_mask):
                    dir_mask[idx] = True
        for idx, rate in enumerate(signed_rate):
            (yaw_buckets["dir_in"] if dir_mask[idx] else yaw_buckets["dir_out"]).append(
                abs(rate)
            )

        processed += 1

    print(f"Processed {processed}/{len(videos)} clips with qpos available")
    return per_class, yaw_buckets


def print_distributions(
    per_class: Dict[str, Dict[str, List[float]]],
    yaw_buckets: Dict[str, List[float]],
) -> None:
    print("\n--- Per-class feature summary (median, p10, p90) ---")
    for behavior in sorted(per_class.keys()):
        feats = per_class[behavior]
        print(f"\n[{behavior}] n_frames={len(feats.get('v_xy', []))}")
        for name in [
            "v_xy",
            "v_z",
            "z_abs",
            "z_rel",
            "yaw_rate",
            "forelimb_var",
            "hindlimb_var",
        ]:
            vals = feats.get(name, [])
            if not vals:
                continue
            med = statistics.median(vals)
            p10 = _percentile(vals, 0.10)
            p90 = _percentile(vals, 0.90)
            print(f"  {name:14s}  med={med: .5f}  p10={p10: .5f}  p90={p90: .5f}")

    print("\n--- Direction (|signed yaw-rate|) distributions ---")
    for bucket in ("dir_in", "dir_out"):
        vals = yaw_buckets[bucket]
        if not vals:
            continue
        med = statistics.median(vals)
        p10 = _percentile(vals, 0.10)
        p90 = _percentile(vals, 0.90)
        print(
            f"  [{bucket:7s}] n={len(vals)}  med={med: .5f}  p10={p10: .5f}  p90={p90: .5f}"
        )


def pick_thresholds(
    per_class: Dict[str, Dict[str, List[float]]],
    yaw_buckets: Dict[str, List[float]],
) -> Dict[str, float]:
    cfg = dict(DEFAULT_CONFIG)

    def p10(cls: str, feat: str) -> float:
        return _percentile(per_class.get(cls, {}).get(feat, []), 0.10)

    def p50(cls: str, feat: str) -> float:
        return _percentile(per_class.get(cls, {}).get(feat, []), 0.50)

    def p90(cls: str, feat: str) -> float:
        return _percentile(per_class.get(cls, {}).get(feat, []), 0.90)

    # walk_xy: midpoint between Walk MEDIAN and max of others' p90.
    # Using median (not p10) makes Walk detection stricter — frames with
    # slight planar drift while turning no longer get labeled Walk.
    walk_p50 = p50("Walk", "v_xy")
    still_p90 = max(
        p90("Immobile", "v_xy"),
        p90("Groom", "v_xy"),
        p90("Rear", "v_xy"),
    )
    if walk_p50 > 0 and still_p90 > 0:
        cfg["walk_xy"] = (walk_p50 + still_p90) / 2
    # Floor to the default so auto-recalibration never drops below the
    # hand-tuned stricter threshold.
    cfg["walk_xy"] = max(cfg["walk_xy"], DEFAULT_CONFIG["walk_xy"])

    still_xy_p90 = p90("Immobile", "v_xy")
    if still_xy_p90 > 0:
        cfg["still_xy"] = still_xy_p90 * 1.1

    # rear_z_abs: push 20% into the Rear distribution above others' p90.
    rear_p10_z_abs = p10("Rear", "z_abs")
    rear_med_z_abs = p50("Rear", "z_abs")
    others_p90_z_abs = max(
        p90("Immobile", "z_abs"),
        p90("Groom", "z_abs"),
        p90("Walk", "z_abs"),
        p90("Turn", "z_abs"),
    )
    if rear_p10_z_abs > others_p90_z_abs > 0:
        cfg["rear_z_abs"] = (rear_p10_z_abs + others_p90_z_abs) / 2
    elif rear_med_z_abs > others_p90_z_abs > 0:
        cfg["rear_z_abs"] = others_p90_z_abs + (rear_med_z_abs - others_p90_z_abs) * 0.2

    # rear_z_delta: separation of Rear z_rel vs others
    rear_p10_z_rel = p10("Rear", "z_rel")
    others_p90_z_rel = max(
        p90("Immobile", "z_rel"),
        p90("Groom", "z_rel"),
        p90("Walk", "z_rel"),
    )
    if rear_p10_z_rel > others_p90_z_rel:
        cfg["rear_z_delta"] = (rear_p10_z_rel + others_p90_z_rel) / 2

    # orient_yaw: separate Turn yaw-rate from others (when strict fails,
    # fall back to pushing 20% into Turn distribution above others' p90).
    turn_p10 = p10("Turn", "yaw_rate")
    turn_med = p50("Turn", "yaw_rate")
    others_p90_yaw = max(
        p90("Immobile", "yaw_rate"),
        p90("Groom", "yaw_rate"),
        p90("Rear", "yaw_rate"),
    )
    if turn_p10 > others_p90_yaw > 0:
        cfg["orient_yaw"] = (turn_p10 + others_p90_yaw) / 2
    elif turn_med > others_p90_yaw > 0:
        cfg["orient_yaw"] = others_p90_yaw + (turn_med - others_p90_yaw) * 0.2

    # groom_limb: Groom has forelimb activity beyond the Rear/Immobile p90.
    groom_p50_limb = p50("Groom", "forelimb_var")
    baseline_p90_limb = max(
        p90("Immobile", "forelimb_var"),
        p90("Rear", "forelimb_var"),
    )
    if groom_p50_limb > baseline_p90_limb > 0:
        cfg["groom_limb"] = (groom_p50_limb + baseline_p90_limb) / 2
    elif baseline_p90_limb > 0:
        cfg["groom_limb"] = baseline_p90_limb * 1.5

    # still_hindlimb: upper bound on hindlimb variance for "planted".
    # Use the p75 of the Immobile hindlimb_var (animals sometimes shift).
    immob_hind = per_class.get("Immobile", {}).get("hindlimb_var", [])
    if immob_hind:
        cfg["still_hindlimb"] = _percentile(immob_hind, 0.75) * 1.5

    # walk_limb: min across fore+hind of (walk_p10 + still_p90)/2.
    walk_fore_p10 = p10("Walk", "forelimb_var")
    walk_hind_p10 = p10("Walk", "hindlimb_var")
    still_fore_p90 = max(
        p90("Immobile", "forelimb_var"),
        p90("Groom", "forelimb_var"),
    )
    still_hind_p90 = max(
        p90("Immobile", "hindlimb_var"),
        p90("Groom", "hindlimb_var"),
    )
    candidates = []
    if walk_fore_p10 > still_fore_p90 > 0:
        candidates.append((walk_fore_p10 + still_fore_p90) / 2)
    if walk_hind_p10 > still_hind_p90 > 0:
        candidates.append((walk_hind_p10 + still_hind_p90) / 2)
    if candidates:
        cfg["walk_limb"] = min(candidates)

    # dir_yaw_thresh: separate |signed yaw-rate| inside Left/Right spans vs outside.
    dir_in = yaw_buckets.get("dir_in", [])
    dir_out = yaw_buckets.get("dir_out", [])
    if dir_in and dir_out:
        in_p10 = _percentile(dir_in, 0.10)
        out_p90 = _percentile(dir_out, 0.90)
        if in_p10 > out_p90 > 0:
            cfg["dir_yaw_thresh"] = (in_p10 + out_p90) / 2
        else:
            in_p50 = _percentile(dir_in, 0.50)
            cfg["dir_yaw_thresh"] = max(out_p90 * 1.1, in_p50 * 0.3)
    # Floor: never drop below the hand-tuned default. Stricter direction
    # calibration is preferred — slow yaw drift stays Straight.
    cfg["dir_yaw_thresh"] = max(cfg["dir_yaw_thresh"], DEFAULT_CONFIG["dir_yaw_thresh"])

    return cfg


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: python scripts/calibrate_thresholds.py <labels.csv> <qpos_dir> <out.json>",
            file=sys.stderr,
        )
        sys.exit(2)
    labels_csv = Path(sys.argv[1])
    csvs_dir = Path(sys.argv[2])
    out_path = Path(sys.argv[3])

    per_class, yaw_buckets = collect(labels_csv, csvs_dir)
    print_distributions(per_class, yaw_buckets)
    cfg = pick_thresholds(per_class, yaw_buckets)

    print("\n--- Chosen thresholds ---")
    for k in sorted(cfg.keys()):
        print(f"  {k}: {cfg[k]}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
