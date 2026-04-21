# TopoMimic-annotation

> Based on the original annotation GUI by Eric Leonardis: https://github.com/ericleonardis/annotation-gui
>
> This fork extends the GUI with a two-track macro-behavior + turn-direction model, qpos-driven auto-labeling, and integration with the TopoMimic / topo-vnl research workflow.

A PyQt5 desktop GUI for frame-accurate annotation of rodent behavior videos. For full feature documentation (keyboard shortcuts, CSV import/export, timeline editing, etc.), see the upstream repo linked above — this fork keeps the core UX and extends it with:

- **Five macro behaviors**: `Immobile, Rear, Turn, Walk, Groom` with hotkeys `I R T W G`.
- **Independent direction track** (`Left / Right / Straight`) above the behavior rows.
- **Auto-labeling** of the behavior track from per-clip qpos (`clip_{i}_{track,stac}_qpos.csv`).
- **Auto-directionality** of the direction track from the same qpos.
- **Snapshot undo/redo** (`Ctrl/Cmd-Z`, `Ctrl/Cmd-Shift-Z`).
- **Drag-to-translate** and **drag-up/down to change behavior** on any segment.

## Install

```bash
conda env create -f environment.yaml
conda activate behavior_gui
```

## Run

```bash
python annotation_GUI.py
```

On first launch, if `sample/videos/` and `sample/csvs/` are present, the GUI loads every clip and runs auto-label + auto-directionality over the set.

## Heuristic spec

See [`docs/auto_labeling.md`](docs/auto_labeling.md) for the per-behavior rule rubric: what each rule looks for, which qpos features feed it, and known failure modes.

## Thresholds

`scripts/calibrate_thresholds.py` reads a converted two-track CSV + a qpos directory and writes `auto_label_config.json`. Re-run after any rig change.
