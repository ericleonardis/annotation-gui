# annotation-gui
# Python Behavior Annotator

A PyQt5-based GUI application for annotating animal behavior in videos, inspired by ChronoViz. Supports multiple videos, customizable behaviors with **editable names and hotkeys**, timeline-based annotation with drag-and-drop editing, and CSV export.

![pythonbehavior](https://github.com/user-attachments/assets/2cc5a964-d362-4bb4-8034-d7287bd58668)


## Features

- **Multi-video support**: Load and annotate multiple videos in one session
- **Flexible behavior tracking**: Add custom behaviors with automatic hotkey assignment
- **Editable behavior table**: Rename behaviors and reassign hotkeys on-the-fly
- **Timeline visualization**: Color-coded behavior segments on an interactive timeline
- **Drag-and-drop editing**: Click and drag segment edges to adjust timing
- **Keyboard shortcuts**: Fast annotation with customizable hotkeys
- **Frame-accurate export**: Export annotations to CSV with frame numbers and timestamps

## Installation

### Prerequisites

- [Git](https://git-scm.com/downloads)
- [Anaconda](https://www.anaconda.com/download) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/ericleonardis/annotation-gui

# Navigate to the project directory
cd AnnotationGUI
```

### Step 2: Create Conda Environment

```bash
# Create the conda environment from the environment.yaml file
conda env create -f environment.yaml

# Activate the environment
conda activate behavior_gui
```

**Alternative: Manual environment creation**

If you prefer to create the environment manually:

```bash
# Create a new conda environment with Python 3.10
conda create -n behavior_gui python=3.10 -c conda-forge

# Activate the environment
conda activate behavior_gui

# Install required packages
pip install pyqt5==5.15.11 opencv-python==4.12.0.88 numpy==2.2.6
```

### Step 3: Verify Installation

```bash
# Test that all dependencies are installed
python -c "import cv2, PyQt5; print('Installation successful!')"
```

## Launching the Application

### From Command Line

```bash
# Make sure the conda environment is activated
conda activate behavior_gui

# Launch the GUI
python annotation_GUI.py
```

### Optional: Create a Launch Script

**For macOS/Linux:**

Create a file called `run_annotator.sh`:

```bash
#!/bin/bash
source ~/anaconda3/etc/profile.d/conda.sh  # Adjust path if using miniconda
conda activate behavior_gui
python annotation_GUI.py
```

Make it executable:

```bash
chmod +x run_annotator.sh
./run_annotator.sh
```

## Usage Guide

### 1. Loading Videos

**Method 1: Using Menu**
1. Click **File** → **Add Video**
2. Select one or multiple video files (`.mp4`, `.avi`, etc.)
3. Videos appear in the left panel

**Method 2: Using Button**
1. Click **Add Video** button in the left panel
2. Select video file(s)

**Supported Formats:**
- MP4, AVI, MOV, MKV (any format supported by OpenCV)

**Managing Videos:**
- Click on a video name to switch between videos
- Click **Remove Video** to delete a video and its annotations

### 2. Managing Behaviors

**Default Behaviors:**
- Immobility (Hotkey: **I**)
- Rear (Hotkey: **R**)
- Groom (Hotkey: **G**)

#### Adding New Behaviors

1. Click **Behaviors** → **Add New Behavior**
2. Enter the behavior name (e.g., "Walk", "Sniff", "Investigate")
3. Hotkey is automatically assigned:
   - First available letter from the behavior name
   - If first letter is taken, tries subsequent letters
   - Falls back to number keys (1-9, 0) if all letters are used
   - Example: "Walk" → **W**, "Water" → **A** (if W is taken)

#### Editing Behavior Names

**The behavior table is fully editable!** To rename a behavior:

1. **Double-click** on the behavior name in the table
2. Type the new name
3. Press **Enter** or click outside the cell
4. All existing annotations automatically update to the new name

**Validation:**
- Empty names are rejected
- Duplicate names are prevented
- All segments across all videos are updated instantly

#### Editing Hotkeys

**Change hotkeys anytime!** To reassign a hotkey:

1. **Double-click** on the hotkey cell in the table
2. Type a single letter (A-Z) or number (0-9)
   - Lowercase letters are automatically converted to uppercase
   - Example: typing "m" becomes "M"
3. Press **Enter** or click outside the cell

**Validation:**
- Must be a single character (letters or numbers only)
- Duplicate hotkeys are prevented
- Symbols and special characters are rejected

**Removing Hotkeys:**
- Clear the hotkey cell (make it empty) to remove a hotkey
- The behavior remains but won't have keyboard shortcut

#### Deleting Behaviors

1. Click **Behaviors** → **Delete Behavior**
2. Select the behavior from the dropdown
3. Confirm deletion (removes from ALL videos)

### 3. Annotating Behaviors

#### Method 1: Hotkey Press-and-Hold (Recommended)

1. Press and hold a behavior's hotkey (e.g., **I** for Immobility)
2. Release the key when behavior ends
3. Segment appears on timeline automatically

**Advantages:**
- Fast and intuitive
- Can annotate multiple behaviors simultaneously
- Works while video is playing or paused
- Hotkeys update immediately if you change them in the table

#### Method 2: Enter Key (Two-Press Method)

1. Select a behavior row in the behavior table
2. Press **Enter** to mark start time
3. Press **Enter** again to mark end time

### 4. Playback Controls

| Key | Action |
|-----|--------|
| **Space** | Play/Pause video |
| **Click timeline** | Scrub to specific time |
| **Drag on timeline** | Scrub while dragging |

### 5. Editing Annotations on Timeline

#### Selecting Segments
- Click on any colored segment to select it
- Selected segments show a yellow border

#### Adjusting Timing
1. **Hover over segment edge** until cursor changes to ↔️
2. **Click and drag** the edge to adjust start or end time
3. **Release mouse** to finalize the change

**Tips:**
- Drag left edge to adjust start time
- Drag right edge to adjust end time
- Middle of segment can be clicked for selection (no dragging)
- Frame numbers automatically recalculate when dragging

#### Deleting Segments
1. Click on a segment to select it
2. Press **Delete** or **Backspace**

### 6. Behavior Table Features

The behavior table shows all behaviors and their hotkeys:

| Behavior Name | Hotkey |
|---------------|--------|
| Immobility    | I      |
| Rear          | R      |
| Groom         | G      |

**Interactive Features:**
- **Double-click any cell** to edit
- **Tab key** to move between cells
- **Enter key** to confirm edits
- **Esc key** to cancel editing (standard Qt behavior)

**Real-time Updates:**
- Timeline rows update when you rename behaviors
- Existing annotations adopt the new name instantly
- Color mappings persist across name changes
- Active annotations (in-progress) are preserved

### 7. Timeline Features

- **Color-coded rows**: Each behavior has its own row with a unique color
- **Behavior labels**: Left side shows behavior names (updated in real-time)
- **Red playhead**: Vertical line shows current video position
- **Transparent segments**: Ongoing annotations (no end time yet) extend to playhead

### 8. Exporting to CSV

1. Click **File** → **Export All to CSV**
2. Choose save location and filename
3. Click **Save**

**CSV Format:**

```csv
Video,Behavior,Start_Time,End_Time,Start_Frame,End_Frame
test_video.mp4,Immobility,1.5,3.2,45,96
test_video.mp4,Rear,5.0,7.8,150,234
video2.mp4,Groom,2.1,4.5,63,135
```

**Important:** CSV export uses the **current** behavior names at export time. If you renamed behaviors, the export will show the new names.

**Column Descriptions:**
- `Video`: Filename of the video
- `Behavior`: Name of the behavior (current name, not original)
- `Start_Time`: Start time in seconds (float)
- `End_Time`: End time in seconds (empty if incomplete)
- `Start_Frame`: Frame number at start
- `End_Frame`: Frame number at end (empty if incomplete)

**Notes:**
- All videos' annotations are exported to a single CSV
- Empty fields indicate incomplete/ongoing annotations
- Frame numbers are calculated from FPS: `frame = time × fps`

## Keyboard Shortcuts Reference

| Shortcut | Action |
|----------|--------|
| **Space** | Play/Pause video |
| **I** | Annotate Immobility (default, editable) |
| **R** | Annotate Rear (default, editable) |
| **G** | Annotate Groom (default, editable) |
| **Custom** | Your custom behavior hotkeys |
| **0-9, A-Z** | Any letter/number you assign |
| **Enter** | Start/Stop annotation (on selected behavior) |
| **Delete** | Delete selected segment |
| **Backspace** | Delete selected segment (alternative) |

**Note:** Hotkeys can be changed anytime by editing the behavior table!

## Workflow Example

1. **Setup:**
   ```bash
   conda activate behavior_gui
   python annotation_GUI.py
   ```

2. **Load video** using File → Add Video

3. **Customize behaviors:**
   - Double-click "Immobility" → Change to "Freezing"
   - Double-click "I" → Change to "F"
   - Add new behavior: Behaviors → Add New Behavior → "Walk"
   - Adjust hotkey: Double-click "W" → Change to "K" if preferred

4. **Annotate:**
   - Press **Space** to start video
   - Hold **F** during freezing periods (your new hotkey)
   - Hold **K** during walking periods
   - Press **Space** to pause if needed

5. **Edit:**
   - Rename "Walk" to "Locomotion" mid-session (all segments update!)
   - Click and drag segment edges to fine-tune timing
   - Delete mistakes with **Delete** key

6. **Export:**
   - File → Export All to CSV
   - CSV contains your finalized behavior names
   - Open CSV in Excel, Python, R, etc.

## Tips and Best Practices

### Annotation Tips
- **Pause frequently** to ensure accurate timing
- **Use hotkeys** for faster annotation (faster than Enter method)
- **Rename behaviors anytime** - don't worry about getting names perfect initially
- **Annotate in passes**: Watch once for each behavior type
- **Review on timeline** before exporting

### Behavior Management Tips
- **Descriptive names**: Use clear names like "GroomingFace" vs "Groom1"
- **Consistent hotkeys**: Keep related behaviors near each other on keyboard (e.g., F-G-H)
- **Remove unused hotkeys**: If you rarely use a behavior's hotkey, clear it to avoid accidents
- **Test new hotkeys**: Press the hotkey after reassigning to ensure it works

### Performance Tips
- Videos stay in memory; close unused videos if RAM is limited
- Large videos (>1GB) may load slowly—be patient
- Timeline updates are fast, but rendering 100+ segments may cause lag
- Editing behavior names is instant (no performance impact)

### Data Management
- **Export regularly** to avoid losing work
- **Use descriptive filenames**: `rat_01_session_2_annotations.csv`
- **Backup your data**: Keep copies of videos and CSVs
- **Document name changes**: Keep notes if you significantly rename behaviors

## Troubleshooting

### Video won't load
- Ensure video codec is supported by OpenCV
- Try converting to MP4 with H.264, these settings will ensure seekability: `ffmpeg -y -i "input.mp4" -c:v libx264 -pix_fmt yuv420p -preset superfast -crf 23 "output.mp4"`

### Hotkey not working after reassignment
- Make sure you pressed Enter after editing the cell
- Check that no warning dialog appeared (duplicate hotkey)
- Letters must be single characters (A-Z, 0-9 only)
- Restart the annotation (press hotkey again) if changed during active annotation

### Can't rename behavior
- Check for error dialog - name might be empty or duplicate
- Make sure you're double-clicking the cell to edit
- Press Enter or Tab to confirm the change

### Timeline shows old behavior name
- This shouldn't happen - contact support if it does (it's a bug!)
- All timeline rows update automatically when you rename

### CSV has old behavior names
- **This is expected!** You may have renamed behaviors after annotating
- Re-export the CSV to get current names
- The app doesn't track historical names

### Application crashes when editing
- Verify conda environment: `conda list`
- Reinstall: `conda env remove -n behavior_gui && conda env create -f environment.yaml`

## Advanced Usage

### Workflow: Iterative Refinement

```plaintext
1. Start with generic names: "Behavior1", "Behavior2"
2. Annotate first pass
3. Review timeline
4. Rename behaviors descriptively: "Behavior1" → "SniffingCorner"
5. Continue annotating with refined understanding
6. Export with final, descriptive names
```

### Batch Processing Multiple Sessions

```python
import pandas as pd

# Combine multiple CSV files
csv_files = ['session1.csv', 'session2.csv', 'session3.csv']
dfs = [pd.read_csv(f) for f in csv_files]
combined = pd.concat(dfs, ignore_index=True)
combined.to_csv('all_sessions.csv', index=False)
```

### Calculating Behavior Durations

```python
import pandas as pd

df = pd.read_csv('annotations.csv')
df['Duration'] = df['End_Time'] - df['Start_Time']

# Total time per behavior
summary = df.groupby('Behavior')['Duration'].sum()
print(summary)
```

### Analyzing Name Changes

If you want to track which behaviors were renamed:

```python
# Keep a log of name changes in a separate file
changes = {
    'Behavior1': 'SniffingCorner',
    'Behavior2': 'Rearing', 
    'WalkFast': 'Locomotion'
}

# Apply retroactively to old CSVs if needed
import pandas as pd
df = pd.read_csv('old_annotations.csv')
df['Behavior'] = df['Behavior'].replace(changes)
df.to_csv('updated_annotations.csv', index=False)
```

## System Requirements

- **OS**: Windows 10+, macOS 10.13+, Linux
- **Python**: 3.10
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: Varies with video size

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-behavior`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to branch (`git push origin feature/new-behavior`)
5. Open a Pull Request

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/AnnotationGUI/issues)
- **Email**: your.email@example.com

## Acknowledgments

- Inspired by [ChronoViz](https://chronoviz.com/)
- Built with PyQt5 and OpenCV
- Color palette inspired by Seaborn/Tableau

---

**Happy Annotating! 🎥📊**
