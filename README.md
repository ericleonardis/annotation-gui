# annotation-gui
# Python Behavior Annotator

A PyQt5-based GUI application for annotating animal behavior in videos, inspired by ChronoViz. Supports multiple videos, customizable behaviors, timeline-based annotation with drag-and-drop editing, and CSV export.

![Untitled](https://github.com/user-attachments/assets/0044020f-ff2f-49b6-aaae-41ec9996dc65)

## Features

- **Multi-video support**: Load and annotate multiple videos in one session
- **Flexible behavior tracking**: Add custom behaviors with automatic hotkey assignment
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
git clone https://github.com/yourusername/AnnotationGUI.git

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

### 2. Adding New Behaviors

**Default Behaviors:**
- Immobility (Hotkey: **I**)
- Rear (Hotkey: **R**)
- Groom (Hotkey: **G**)

**To Add a Custom Behavior:**
1. Click **Behaviors** → **Add New Behavior**
2. Enter the behavior name (e.g., "Walk", "Sniff", "Investigate")
3. Hotkey is automatically assigned:
   - First available letter from the behavior name
   - If first letter is taken, tries subsequent letters
   - Example: "Walk" → **W**, "Water" → **A** (if W is taken)

**To Delete a Behavior:**
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

#### Method 2: Enter Key (Two-Press Method)

1. Select a behavior from the behavior list (right panel)
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

### 6. Timeline Features

- **Color-coded rows**: Each behavior has its own row with a unique color
- **Behavior labels**: Left side shows behavior names
- **Red playhead**: Vertical line shows current video position
- **Transparent segments**: Ongoing annotations (no end time yet) extend to playhead

### 7. Exporting to CSV

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

**Column Descriptions:**
- `Video`: Filename of the video
- `Behavior`: Name of the behavior
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
| **I** | Annotate Immobility (default) |
| **R** | Annotate Rear (default) |
| **G** | Annotate Groom (default) |
| **Custom** | Your custom behavior hotkeys |
| **Enter** | Start/Stop annotation (two-press method) |
| **Delete** | Delete selected segment |
| **Backspace** | Delete selected segment (alternative) |

## Workflow Example

1. **Setup:**
   ```bash
   conda activate behavior_gui
   python annotation_GUI.py
   ```

2. **Load video** using File → Add Video

3. **Add behaviors** (if needed):
   - Behaviors → Add New Behavior → "Walk"
   - Behaviors → Add New Behavior → "Sniff"

4. **Annotate:**
   - Press **Space** to start video
   - Hold **I** during immobility periods
   - Hold **W** during walking periods
   - Press **Space** to pause if needed

5. **Edit:**
   - Click and drag segment edges to fine-tune timing
   - Delete mistakes with **Delete** key

6. **Export:**
   - File → Export All to CSV
   - Open CSV in Excel, Python, R, etc.

## Tips and Best Practices

### Annotation Tips
- **Pause frequently** to ensure accurate timing
- **Use hotkeys** for faster annotation (faster than Enter method)
- **Annotate in passes**: Watch once for each behavior type
- **Review on timeline** before exporting

### Performance Tips
- Videos stay in memory; close unused videos if RAM is limited
- Large videos (>1GB) may load slowly—be patient
- Timeline updates are fast, but rendering 100+ segments may cause lag

### Data Management
- **Export regularly** to avoid losing work
- **Use descriptive filenames**: `rat_01_session_2_annotations.csv`
- **Backup your data**: Keep copies of videos and CSVs

## Troubleshooting

### Video won't load
- Ensure video codec is supported by OpenCV
- Try converting to MP4 with H.264: `ffmpeg -i input.avi -c:v libx264 output.mp4`

### Hotkey not working
- Check if letter is already assigned to another behavior
- Use Behaviors → Add New Behavior to see assigned hotkeys
- Some letters may be reserved by the OS (e.g., Cmd+Q on Mac)

### Timeline lag with many segments
- Export and start a new session
- Reduce video resolution (timeline doesn't need high-res)

### CSV has empty End_Time/End_Frame
- You have incomplete annotations (started but not finished)
- Press the hotkey again to finish, or delete the segment

### Application crashes on startup
- Verify conda environment: `conda list`
- Reinstall: `conda env remove -n behavior_gui && conda env create -f environment.yaml`

## Advanced Usage

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
