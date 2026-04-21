"""Transform legacy behavior-label CSVs to the new two-track schema.

Old schema (input):
    Video, Behavior, Start_Time, End_Time, Start_Frame, End_Frame
    - Behaviors: Immobility, Grooming, Orienting, Walking,
                 Supported Rear, Unsupported Rear, Left Turn, Right Turn

New schema (output):
    Video, Track, Label, Start_Time, End_Time, Start_Frame, End_Frame
    - Track=behavior with Label in {Immobile, Rear, Turn, Walk, Groom}
    - Track=direction with Label in {Left, Right}
      (Straight is NOT emitted by the converter; auto-directionality fills
      gaps later.)

Rules:
    1. Supported Rear + Unsupported Rear -> Rear
    2. Immobility -> Immobile
    3. Walking -> Walk
    4. Grooming -> Groom
    5. Orienting -> Turn
    6. Left Turn  -> direction-track row labeled Left
       Right Turn -> direction-track row labeled Right
    7. No splitting of behavior segments, no flag; behavior durations are
       preserved verbatim.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, List

RENAME_MAP: Dict[str, str] = {
    "Immobility": "Immobile",
    "Walking": "Walk",
    "Grooming": "Groom",
    "Orienting": "Turn",
    "Supported Rear": "Rear",
    "Unsupported Rear": "Rear",
}

DIRECTION_MAP: Dict[str, str] = {
    "Left Turn": "Left",
    "Right Turn": "Right",
}

FIELDNAMES = [
    "Video",
    "Track",
    "Label",
    "Start_Time",
    "End_Time",
    "Start_Frame",
    "End_Frame",
]


def _parse_int(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        return str(int(float(raw)))
    except ValueError:
        return ""


def transform_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Transform flat legacy rows to new-schema rows.

    Input rows follow the 6-column schema. Output rows follow the 7-column
    schema with a Track column.
    """
    out: List[Dict[str, str]] = []
    for r in rows:
        video = r["Video"]
        beh = (r.get("Behavior") or "").strip()
        ts = (r.get("Start_Time") or "").strip()
        te = (r.get("End_Time") or "").strip()
        fs = _parse_int(r.get("Start_Frame", ""))
        fe = _parse_int(r.get("End_Frame", ""))

        if beh in DIRECTION_MAP:
            track = "direction"
            label = DIRECTION_MAP[beh]
        elif beh in RENAME_MAP:
            track = "behavior"
            label = RENAME_MAP[beh]
        else:
            track = "behavior"
            label = beh

        out.append(
            {
                "Video": video,
                "Track": track,
                "Label": label,
                "Start_Time": ts,
                "End_Time": te,
                "Start_Frame": fs,
                "End_Frame": fe,
            }
        )
    return out


def convert_file(src: Path, dst: Path) -> tuple[int, int]:
    """Read old-schema CSV from src, write new-schema CSV to dst.

    Returns (in_rows, out_rows).
    """
    with open(src, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    out = transform_rows(rows)

    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in out:
            writer.writerow(r)

    return len(rows), len(out)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python convert_labels.py <old.csv> <new.csv>", file=sys.stderr)
        sys.exit(2)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    n_in, n_out = convert_file(src, dst)
    print(f"Read {n_in} rows, wrote {n_out} rows -> {dst}")


if __name__ == "__main__":
    main()
