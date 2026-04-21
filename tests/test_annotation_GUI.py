import pytest
import csv
import os
import tempfile

os.environ.setdefault("ANNOTATION_GUI_NO_AUTOLOAD", "1")

from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest
import cv2
import numpy as np

from annotation_GUI import AnnotatorGUI, BehaviorSegment, TimelineWidget


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for all tests.

    Creates a singleton QApplication instance that persists for the entire
    test session. Required for testing PyQt5 GUI components.

    Args:
        None

    Returns:
        QApplication: The application instance used for all GUI tests.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_video(tmp_path):
    """Create a temporary test video file.

    Generates a 10-second MP4 video at 30 FPS with 640x480 resolution.
    Each frame has a different color pattern for visual distinction.

    Args:
        tmp_path: pytest fixture providing temporary directory path.

    Returns:
        str: Absolute path to the created test video file.
    """
    video_path = tmp_path / "test_video.mp4"

    # Create a simple test video
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 30.0
    frame_size = (640, 480)
    duration_frames = 300  # 10 seconds at 30fps

    out = cv2.VideoWriter(str(video_path), fourcc, fps, frame_size)

    for i in range(duration_frames):
        # Create colored frames
        frame = np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
        frame[:, :] = (i % 255, (i * 2) % 255, (i * 3) % 255)
        out.write(frame)

    out.release()

    return str(video_path)


@pytest.fixture
def temp_csv(tmp_path):
    """Create a temporary CSV file path.

    Args:
        tmp_path: pytest fixture providing temporary directory path.

    Returns:
        str: Absolute path where CSV file can be written.
    """
    return str(tmp_path / "test_export.csv")


@pytest.fixture
def gui(qapp, temp_video):
    """Create GUI instance with a loaded video.

    Initializes AnnotatorGUI, shows the window, and loads a test video
    using mocked file dialogs. Handles cleanup after test completion.

    Args:
        qapp: pytest fixture providing QApplication instance.
        temp_video: pytest fixture providing path to test video.

    Returns:
        AnnotatorGUI: Initialized GUI instance with loaded test video.
    """
    window = AnnotatorGUI()
    window.show()

    # Mock the file dialog to return our test video
    with patch(
        "annotation_GUI.QFileDialog.getOpenFileNames", return_value=([temp_video], "")
    ):
        with patch("annotation_GUI.QMessageBox.information"):
            window.load_video()

    yield window

    # Cleanup
    if window.cap:
        window.cap.release()
    window.close()


class TestBehaviorSegment:
    """Test BehaviorSegment class."""

    def test_segment_creation(self):
        """Test creating a behavior segment.

        Verifies that BehaviorSegment initializes correctly with all
        attributes set to expected values.

        Args:
            None

        Returns:
            None
        """
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        assert seg.name == "Immobile"
        assert seg.start_time == 1.0
        assert seg.end_time == 2.0
        assert seg.start_frame == 30
        assert seg.end_frame == 60
        assert seg.color is not None

    def test_color_assignment(self):
        """Test that segments get unique colors.

        Verifies that different behavior types receive distinct colors
        from the color palette.

        Args:
            None

        Returns:
            None
        """
        seg1 = BehaviorSegment("NewBehavior1", 0, 1)
        seg2 = BehaviorSegment("NewBehavior2", 1, 2)
        assert seg1.color != seg2.color

    def test_color_persistence(self):
        """Test that same behavior gets same color.

        Verifies that multiple segments of the same behavior type
        share the same color.

        Args:
            None

        Returns:
            None
        """
        seg1 = BehaviorSegment("TestBehavior", 0, 1)
        seg2 = BehaviorSegment("TestBehavior", 2, 3)
        assert seg1.color == seg2.color

    def test_remove_behavior_color(self):
        """Test removing behavior color mapping.

        Verifies that color mapping can be removed and freed up for reuse.

        Args:
            None

        Returns:
            None
        """
        test_behavior = "RemoveMe"
        seg = BehaviorSegment(test_behavior, 0, 1)
        original_color = seg.color

        BehaviorSegment.remove_behavior_color(test_behavior)
        assert test_behavior not in BehaviorSegment._color_map


class TestTimelineWidget:
    """Test TimelineWidget class."""

    def test_timeline_initialization(self, qapp):
        """Test timeline widget initialization.

        Verifies that TimelineWidget initializes with correct default values.

        Args:
            qapp: pytest fixture providing QApplication instance.

        Returns:
            None
        """
        timeline = TimelineWidget()
        assert timeline.duration == 1.0
        assert timeline.current_time == 0.0
        assert len(timeline.segments) == 0
        assert len(timeline.behavior_types) == 5

    def test_update_behavior_types(self, qapp):
        """Test updating behavior types.

        Verifies that behavior type list can be updated dynamically.

        Args:
            qapp: pytest fixture providing QApplication instance.

        Returns:
            None
        """
        timeline = TimelineWidget()
        new_behaviors = ["Walk", "Run", "Jump"]
        timeline.update_behavior_types(new_behaviors)
        assert timeline.behavior_types == new_behaviors

    def test_get_behavior_row(self, qapp):
        """Test getting behavior row position.

        Verifies that Y-coordinates for behavior rows are calculated correctly.

        Args:
            qapp: pytest fixture providing QApplication instance.

        Returns:
            None
        """
        timeline = TimelineWidget()
        origin = timeline.behaviors_origin_y
        # First behavior row starts at origin (below direction strip).
        row = timeline.get_behavior_row("Immobile")
        assert row == origin

        row = timeline.get_behavior_row("Rear")
        assert row == origin + (timeline.row_height + 5)

    def test_segment_selection(self, qapp):
        """Test segment selection.

        Verifies that segments can be selected on the timeline.

        Args:
            qapp: pytest fixture providing QApplication instance.

        Returns:
            None
        """
        timeline = TimelineWidget()
        timeline.duration = 10.0

        seg = BehaviorSegment("Immobile", 1.0, 2.0)
        timeline.segments.append(seg)

        timeline.selected_segment = seg
        assert timeline.selected_segment == seg

    def test_delete_selected_segment(self, qapp):
        """Test deleting selected segment.

        Verifies that selected segments can be deleted from timeline.

        Args:
            qapp: pytest fixture providing QApplication instance.

        Returns:
            None
        """
        timeline = TimelineWidget()
        seg = BehaviorSegment("Immobile", 1.0, 2.0)
        timeline.segments.append(seg)
        timeline.selected_segment = seg

        result = timeline.delete_selected_segment()
        assert result is True
        assert len(timeline.segments) == 0
        assert timeline.selected_segment is None


class TestAnnotatorGUI:
    """Test AnnotatorGUI main window."""

    def test_gui_initialization(self, qapp):
        """Test GUI initialization.

        Verifies that AnnotatorGUI initializes with correct default state.

        Args:
            qapp: pytest fixture providing QApplication instance.

        Returns:
            None
        """
        window = AnnotatorGUI()
        assert window.windowTitle() == "Python Behavior Annotator"
        assert len(window.videos) == 0
        assert window.current_video_name is None
        assert len(window.behavior_types) == 5

    def test_load_single_video(self, gui):
        """Test loading a single video.

        Verifies that video loads correctly with proper FPS and duration.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        assert len(gui.videos) == 1
        assert gui.current_video_name is not None
        assert gui.cap is not None

        video_data = gui.videos[gui.current_video_name]
        assert video_data["fps"] == 30.0
        assert video_data["duration"] == pytest.approx(10.0, rel=0.1)

    def test_load_multiple_videos(self, qapp, temp_video, tmp_path):
        """Test loading multiple videos.

        Verifies that multiple videos can be loaded simultaneously.

        Args:
            qapp: pytest fixture providing QApplication instance.
            temp_video: pytest fixture providing path to first test video.
            tmp_path: pytest fixture providing temporary directory path.

        Returns:
            None
        """
        # Create second video
        video2_path = tmp_path / "test_video2.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(video2_path), fourcc, 30.0, (640, 480))
        for i in range(150):  # 5 seconds
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

        window = AnnotatorGUI()
        window.show()

        # Mock loading multiple videos
        with patch(
            "annotation_GUI.QFileDialog.getOpenFileNames",
            return_value=([temp_video, str(video2_path)], ""),
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                window.load_video()

        assert len(window.videos) == 2

        window.close()

    def test_switch_video(self, gui, tmp_path):
        """Test switching between videos.

        Verifies that annotations are saved when switching videos and
        that each video maintains its own annotation state.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            tmp_path: pytest fixture providing temporary directory path.

        Returns:
            None
        """
        # Add annotation to first video
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)

        # Create and load second video
        video2_path = tmp_path / "test_video2.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(video2_path), fourcc, 30.0, (640, 480))
        for i in range(150):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

        with patch(
            "annotation_GUI.QFileDialog.getOpenFileNames",
            return_value=([str(video2_path)], ""),
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.load_video()

        # Switch to second video
        gui.video_list.setCurrentRow(1)
        QTest.qWait(100)

        # First video's segments should be saved
        first_video_name = list(gui.videos.keys())[0]
        assert len(gui.videos[first_video_name]["segments"]) == 1

        # Second video should have no segments
        assert len(gui.timeline.segments) == 0

    def test_remove_video(self, gui):
        """Test removing a video.

        Verifies that videos can be removed from the application with
        proper cleanup.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        video_name = gui.current_video_name

        with patch("annotation_GUI.QMessageBox.question", return_value=QMessageBox.Yes):
            gui.remove_video()

        assert video_name not in gui.videos
        assert gui.video_list.count() == 0

    def test_add_behavior(self, gui):
        """Test adding a new behavior.

        Verifies that new behavior types can be added with automatic
        hotkey assignment.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        initial_count = len(gui.behavior_types)

        with patch("annotation_GUI.QInputDialog.getText", return_value=("Sniff", True)):
            gui.add_new_behavior()

        assert len(gui.behavior_types) == initial_count + 1
        assert "Sniff" in gui.behavior_types
        assert "Sniff" in gui.behavior_hotkeys

    def test_delete_behavior(self, gui):
        """Test deleting a behavior.

        Verifies that behavior types can be deleted and all associated
        segments are removed from all videos.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Add a segment
        seg = BehaviorSegment("Immobile", 1.0, 2.0)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        with patch(
            "annotation_GUI.QInputDialog.getItem", return_value=("Immobile", True)
        ):
            with patch(
                "annotation_GUI.QMessageBox.question", return_value=QMessageBox.Yes
            ):
                gui.delete_behavior()

        assert "Immobile" not in gui.behavior_types
        assert len(gui.timeline.segments) == 0

    def test_annotation_with_hotkeys(self, gui):
        """Test creating annotation with hotkeys.

        Verifies that pressing and releasing behavior hotkeys creates
        annotations with correct start and end times.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Simulate pressing 'I' key (Immobility)
        QTest.keyPress(gui, Qt.Key_I)
        QTest.qWait(100)

        assert len(gui.timeline.segments) == 1
        assert gui.timeline.segments[0].name == "Immobile"
        assert gui.timeline.segments[0].start_time is not None

        # Simulate releasing 'I' key
        QTest.keyRelease(gui, Qt.Key_I)
        QTest.qWait(100)

        assert gui.timeline.segments[0].end_time is not None

    def test_annotation_with_enter_key(self, gui):
        """Test creating annotation with Enter key.

        Verifies that two-press Enter annotation method works correctly.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        gui.behavior_list.setCurrentRow(0)

        # First press - start annotation
        QTest.keyPress(gui.behavior_list, Qt.Key_Return)
        QTest.qWait(100)

        assert len(gui.timeline.segments) == 1
        assert gui.timeline.segments[0].end_time is None

        # Second press - end annotation
        QTest.keyPress(gui.behavior_list, Qt.Key_Return)
        QTest.qWait(100)

        assert gui.timeline.segments[0].end_time is not None

    def test_delete_segment_with_keyboard(self, gui):
        """Test deleting segment with Delete key.

        Verifies that selected segments can be deleted via keyboard.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        seg = BehaviorSegment("Immobile", 1.0, 2.0)
        gui.timeline.segments.append(seg)
        gui.timeline.selected_segment = seg

        QTest.keyPress(gui, Qt.Key_Delete)
        QTest.qWait(100)

        assert len(gui.timeline.segments) == 0

    def test_play_pause_toggle(self, gui):
        """Test play/pause functionality.

        Verifies that Space key toggles video playback state.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        assert gui.is_playing is False

        QTest.keyPress(gui, Qt.Key_Space)
        QTest.qWait(100)

        assert gui.is_playing is True

        QTest.keyPress(gui, Qt.Key_Space)
        QTest.qWait(100)

        assert gui.is_playing is False


class TestSegmentModification:
    """Test segment modification and frame recalculation."""

    def test_segment_drag_updates_frames(self, gui):
        """Test that dragging segment edges updates frame numbers.

        Verifies that modifying segment end time recalculates end frame
        number based on video FPS.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Create a segment
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)
        gui.timeline.duration = 10.0

        # Simulate dragging the end edge
        seg.end_time = 3.0
        gui.on_segment_modified(seg)

        # Frame should be recalculated: 3.0 seconds * 30 fps = 90 frames
        assert seg.end_frame == 90
        assert seg.start_frame == 30

    def test_segment_start_drag_updates_frames(self, gui):
        """Test dragging start edge updates start frame.

        Verifies that modifying segment start time recalculates start frame
        number based on video FPS.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)
        gui.timeline.duration = 10.0

        # Drag start edge
        seg.start_time = 0.5
        gui.on_segment_modified(seg)

        # 0.5 seconds * 30 fps = 15 frames
        assert seg.start_frame == 15
        assert seg.end_frame == 60


class TestCSVExport:
    """Test CSV export functionality."""

    def test_export_empty(self, gui, temp_csv):
        """Test exporting with no annotations.

        Verifies that CSV export creates valid file with header when
        no annotations exist.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        assert os.path.exists(temp_csv)

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 1  # Only header
            assert rows[0] == [
                "Video",
                "Track",
                "Label",
                "Start_Time",
                "End_Time",
                "Start_Frame",
                "End_Frame",
            ]

    def test_export_single_annotation(self, gui, temp_csv):
        """Test exporting single annotation.

        Verifies that single annotation exports correctly with all fields.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Add annotation
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2  # Header + 1 data row
            assert rows[1][1] == "behavior"
            assert rows[1][2] == "Immobile"
            assert float(rows[1][3]) == 1.0
            assert float(rows[1][4]) == 2.0
            assert int(rows[1][5]) == 30
            assert int(rows[1][6]) == 60

    def test_export_multiple_annotations(self, gui, temp_csv):
        """Test exporting multiple annotations.

        Verifies that multiple annotations from same video export correctly.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        seg1 = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        seg2 = BehaviorSegment("Rear", 3.0, 4.0, 90, 120)
        seg3 = BehaviorSegment("Groom", 5.0, 6.0, 150, 180)

        gui.timeline.segments.extend([seg1, seg2, seg3])
        gui.videos[gui.current_video_name]["segments"] = [seg1, seg2, seg3]

        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 4  # Header + 3 data rows

    def test_export_multiple_videos(self, gui, temp_csv, tmp_path):
        """Test exporting annotations from multiple videos.

        Verifies that annotations from multiple videos export together
        with video names correctly associated.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.
            tmp_path: pytest fixture providing temporary directory path.

        Returns:
            None
        """
        # Add annotation to first video
        seg1 = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg1)

        # Create and load second video
        video2_path = tmp_path / "video2.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(video2_path), fourcc, 30.0, (640, 480))
        for i in range(150):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

        with patch(
            "annotation_GUI.QFileDialog.getOpenFileNames",
            return_value=([str(video2_path)], ""),
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.load_video()

        # Add annotation to second video
        gui.video_list.setCurrentRow(1)
        QTest.qWait(100)
        seg2 = BehaviorSegment("Rear", 3.0, 4.0, 90, 120)
        gui.timeline.segments.append(seg2)

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 3  # Header + 2 data rows

            video_names = [row[0] for row in rows[1:]]
            assert len(set(video_names)) == 2  # Two different videos

    def test_export_modified_segment_frames(self, gui, temp_csv):
        """Test that modified segment frame numbers are exported correctly.

        Verifies that frame recalculation after segment modification
        persists to CSV export.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Create segment
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)

        # Modify the segment
        seg.end_time = 3.0
        gui.on_segment_modified(seg)

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            # Check that frame was recalculated: 3.0 * 30 = 90
            assert int(rows[1][6]) == 90

    def test_export_incomplete_segment(self, gui, temp_csv):
        """Test exporting segment without end time.

        Verifies that incomplete annotations (ongoing at export time)
        export with empty end fields.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        seg = BehaviorSegment("Immobile", 1.0, None, 30, None)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert rows[1][4] == ""  # Empty end time
            assert rows[1][6] == ""  # Empty end frame

    def test_export_after_deleting_segment(self, gui, temp_csv):
        """Test CSV export after deleting a segment.

        Verifies that deleted segments don't appear in CSV export.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Add three segments
        seg1 = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        seg2 = BehaviorSegment("Rear", 3.0, 4.0, 90, 120)
        seg3 = BehaviorSegment("Groom", 5.0, 6.0, 150, 180)

        gui.timeline.segments.extend([seg1, seg2, seg3])
        gui.videos[gui.current_video_name]["segments"] = [seg1, seg2, seg3]

        # Delete the middle segment
        gui.timeline.selected_segment = seg2
        gui.timeline.delete_selected_segment()
        gui.videos[gui.current_video_name]["segments"] = gui.timeline.segments.copy()

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 3  # Header + 2 remaining segments

            # Verify the remaining segments
            behaviors = [row[2] for row in rows[1:]]
            assert "Immobile" in behaviors
            assert "Groom" in behaviors
            assert "Rear" not in behaviors

    def test_export_with_long_video_duration(self, qapp, tmp_path, temp_csv):
        """Test CSV with very long video durations.

        Verifies that hour-long videos with large frame/time numbers
        export correctly without overflow or precision issues.

        Args:
            qapp: pytest fixture providing QApplication instance.
            tmp_path: pytest fixture providing temporary directory path.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Create a long video (simulating 1 hour)
        long_video_path = tmp_path / "long_video.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        fps = 30.0
        duration_seconds = 3600  # 1 hour

        # We'll create a video with metadata but minimal frames
        out = cv2.VideoWriter(str(long_video_path), fourcc, fps, (640, 480))

        # Write just a few frames (OpenCV will allow seeking to any position)
        for i in range(90):  # 3 seconds of actual frames
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

        # Manually set up a video with long duration
        window = AnnotatorGUI()
        window.show()

        # Mock loading the video
        with patch(
            "annotation_GUI.QFileDialog.getOpenFileNames",
            return_value=([str(long_video_path)], ""),
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                window.load_video()

        # Manually set long duration
        video_name = window.current_video_name
        window.videos[video_name]["duration"] = 3600.0  # 1 hour
        window.timeline.duration = 3600.0

        # Add annotations at various points throughout the hour
        seg1 = BehaviorSegment("Immobile", 600.0, 900.0, 18000, 27000)  # 10-15 min
        seg2 = BehaviorSegment("Rear", 1800.0, 2100.0, 54000, 63000)  # 30-35 min
        seg3 = BehaviorSegment("Groom", 3300.0, 3500.0, 99000, 105000)  # 55-58 min

        window.timeline.segments.extend([seg1, seg2, seg3])
        window.videos[video_name]["segments"] = [seg1, seg2, seg3]

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                window.export_csv()

        # Verify export
        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 4  # Header + 3 segments

            # Check that large times are correctly exported
            assert float(rows[1][3]) == 600.0
            assert float(rows[1][4]) == 900.0
            assert int(rows[1][5]) == 18000
            assert int(rows[1][6]) == 27000

            assert float(rows[3][3]) == 3300.0
            assert int(rows[3][6]) == 105000

        window.close()

    def test_export_with_special_characters_in_behavior_names(self, gui, temp_csv):
        """Test CSV with special characters in behavior names.

        Verifies that CSV properly escapes special characters like
        quotes, commas, ampersands, etc.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Create behaviors with various special characters
        special_behaviors = [
            "Walk & Run",
            "Groom (Head)",
            "Rear-Up",
            "Rest/Sleep",
            'Jump "High"',
            "Sniff, Investigate",
            "Behavior #1",
            "Test'Behavior",
        ]

        segments = []
        start_time = 1.0

        for behavior in special_behaviors:
            seg = BehaviorSegment(
                behavior,
                start_time,
                start_time + 1.0,
                int(start_time * 30),
                int((start_time + 1.0) * 30),
            )
            segments.append(seg)
            start_time += 2.0

        gui.timeline.segments.extend(segments)
        gui.videos[gui.current_video_name]["segments"] = segments

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        # Verify all special character behaviors are exported correctly
        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == len(special_behaviors) + 1  # Header + all behaviors

            exported_behaviors = [row[2] for row in rows[1:]]
            for behavior in special_behaviors:
                assert behavior in exported_behaviors

    def test_export_with_read_only_file(self, gui, tmp_path):
        """Test CSV export with file permission errors.

        Verifies that export handles read-only file errors gracefully
        without crashing the application.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            tmp_path: pytest fixture providing temporary directory path.

        Returns:
            None
        """
        read_only_csv = tmp_path / "readonly.csv"

        # Create a read-only file
        read_only_csv.touch()
        read_only_csv.chmod(0o444)  # Read-only permissions

        try:
            # Attempt to export to read-only file
            with patch(
                "annotation_GUI.QFileDialog.getSaveFileName",
                return_value=(str(read_only_csv), ""),
            ):
                # Add a segment
                seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
                gui.timeline.segments.append(seg)
                gui.videos[gui.current_video_name]["segments"] = [seg]

                # The export should fail (either silently or with an error)
                # We're testing that it doesn't crash the application
                try:
                    gui.export_csv()
                except (PermissionError, IOError):
                    # Expected behavior - permission denied
                    pass
        finally:
            # Restore write permissions for cleanup
            read_only_csv.chmod(0o644)

    def test_export_to_nonexistent_directory(self, gui):
        """Test CSV export to a directory that doesn't exist.

        Verifies that export handles nonexistent paths gracefully
        without crashing the application.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        nonexistent_path = "/nonexistent/directory/test.csv"

        # Add a segment
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        # Attempt to export to nonexistent directory
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName",
            return_value=(nonexistent_path, ""),
        ):
            try:
                gui.export_csv()
            except (FileNotFoundError, IOError):
                # Expected behavior - directory doesn't exist
                pass

    def test_export_with_unicode_behavior_names(self, gui, temp_csv):
        """Test CSV with Unicode characters in behavior names.

        Verifies that emoji, international characters, and Unicode symbols
        export correctly with UTF-8 encoding.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        unicode_behaviors = [
            "Grooming 🧹",
            "Walking →",
            "Resting 😴",
            "探索",  # Chinese characters
            "Поведение",  # Russian characters
            "Comportement",  # French with accent
        ]

        segments = []
        start_time = 1.0

        for behavior in unicode_behaviors:
            seg = BehaviorSegment(
                behavior,
                start_time,
                start_time + 1.0,
                int(start_time * 30),
                int((start_time + 1.0) * 30),
            )
            segments.append(seg)
            start_time += 2.0

        gui.timeline.segments.extend(segments)
        gui.videos[gui.current_video_name]["segments"] = segments

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName",
            return_value=(temp_csv, ""),
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        # Verify Unicode behaviors are exported correctly
        with open(temp_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

            exported_behaviors = [row[2] for row in rows[1:]]
            for behavior in unicode_behaviors:
                assert behavior in exported_behaviors

    def test_export_preserves_segment_order(self, gui, temp_csv):
        """Test that CSV export preserves the order of segments.

        Verifies that segments are exported in the order they were added,
        not sorted by time or behavior name.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Add segments in non-chronological order
        seg3 = BehaviorSegment("Groom", 5.0, 6.0, 150, 180)
        seg1 = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        seg2 = BehaviorSegment("Rear", 3.0, 4.0, 90, 120)

        # Add in specific order
        gui.timeline.segments.extend([seg3, seg1, seg2])
        gui.videos[gui.current_video_name]["segments"] = [seg3, seg1, seg2]

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        # Verify order is preserved
        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)

            # Check that segments appear in the same order they were added
            assert rows[1][2] == "Groom"
            assert rows[2][2] == "Immobile"
            assert rows[3][2] == "Rear"

    def test_export_with_zero_duration_segment(self, gui, temp_csv):
        """Test exporting segment with zero or very small duration.

        Verifies that segments with minimal duration (e.g., 1ms) export
        correctly without errors or precision loss.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Create a segment with very small duration
        seg = BehaviorSegment("Immobile", 1.0, 1.001, 30, 30)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        # Export
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        # Verify it exports correctly
        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert float(rows[1][3]) == 1.0
            assert float(rows[1][4]) == 1.001


class TestVideoSeek:
    """Test video seeking functionality."""

    def test_seek_to_time(self, gui):
        """Test seeking to specific time.

        Verifies that programmatic seeking moves video to correct position.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        initial_time = gui.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

        gui.seek_video(5.0)  # Seek to 5 seconds
        QTest.qWait(100)

        current_time = gui.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        assert current_time == pytest.approx(5.0, abs=0.1)

    def test_timeline_click_seeks(self, gui):
        """Test clicking timeline seeks video.

        Verifies that clicking on timeline scrubs video to corresponding
        time position.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Simulate clicking at 50% of timeline
        timeline_width = gui.timeline.width()
        click_x = timeline_width // 2
        click_y = 25

        QTest.mouseClick(gui.timeline, Qt.LeftButton, pos=QPoint(click_x, click_y))
        QTest.qWait(100)

        current_time = gui.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        expected_time = gui.timeline.duration / 2
        assert current_time == pytest.approx(expected_time, abs=0.5)


class TestUIElements:
    """Test UI elements and interactions."""

    def test_behavior_list_updated_on_add(self, gui):
        """Test behavior list updates when adding behavior.

        Verifies that UI list widget displays newly added behaviors.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        initial_count = gui.behavior_list.count()

        with patch("annotation_GUI.QInputDialog.getText", return_value=("Sniff", True)):
            gui.add_new_behavior()

        assert gui.behavior_list.count() == initial_count + 1

    def test_video_list_updated_on_load(self, gui):
        """Test video list shows loaded videos.

        Verifies that video list widget displays loaded video filenames.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        assert gui.video_list.count() == 1
        assert gui.video_list.item(0).text() == os.path.basename(
            gui.videos[gui.current_video_name]["path"]
        )

    def test_play_button_exists(self, gui):
        """Test play button exists and is clickable.

        Verifies that play/pause button is present and functional,
        toggling playback state when clicked.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        assert gui.btn_play is not None
        assert gui.btn_play.text() == "Play/Pause (Space)"

        # Click should toggle play state
        initial_state = gui.is_playing
        gui.btn_play.click()
        QTest.qWait(100)
        assert gui.is_playing != initial_state


class TestBehaviorTableEditing:
    """Test behavior table editing functionality."""

    def test_modify_behavior_name_in_table(self, gui):
        """Test modifying a behavior name in the table.

        Verifies that editing a behavior name in the table updates
        all occurrences throughout the application.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Create a segment with original behavior name
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        # Find Immobility in the table (should be row 0)
        old_name = "Immobile"
        new_name = "Freezing"

        # Get the item and modify it
        name_item = gui.behavior_table.item(0, 0)
        assert name_item.text() == old_name

        # Simulate editing the cell
        name_item.setText(new_name)
        gui.on_behavior_table_changed(name_item)

        # Verify behavior type list updated
        assert new_name in gui.behavior_types
        assert old_name not in gui.behavior_types

        # Verify segment name updated
        assert gui.timeline.segments[0].name == new_name

        # Verify hotkey mapping updated
        assert new_name in gui.behavior_hotkeys
        assert old_name not in gui.behavior_hotkeys

        # Verify legacy list updated
        list_items = [
            gui.behavior_list.item(i).text() for i in range(gui.behavior_list.count())
        ]
        assert any(new_name in item for item in list_items)
        assert not any(old_name in item for item in list_items)

    def test_modify_behavior_name_exports_correctly(self, gui, temp_csv):
        """Test that modified behavior names export correctly to CSV.

        Verifies that after renaming a behavior, the CSV export contains
        the new name rather than the old one.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Create segment with original name
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        # Modify the behavior name in the table
        new_name = "StandingStill"
        name_item = gui.behavior_table.item(0, 0)
        name_item.setText(new_name)
        gui.on_behavior_table_changed(name_item)

        # Export to CSV
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        # Verify CSV contains new name
        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2  # Header + 1 segment
            assert rows[1][2] == new_name
            assert rows[1][2] != "Immobile"

    def test_modify_hotkey_in_table(self, gui):
        """Test modifying a hotkey in the table.

        Verifies that editing a hotkey in the table updates the
        hotkey mapping and allows the new key to trigger annotations.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Original hotkey for Immobility is 'I' (Qt.Key_I)
        behavior = "Immobile"
        old_key = Qt.Key_I
        new_key_text = "M"
        new_key = Qt.Key_M

        # Verify original hotkey
        assert gui.behavior_hotkeys[behavior] == old_key

        # Modify hotkey in table (row 0, column 1)
        hotkey_item = gui.behavior_table.item(0, 1)
        hotkey_item.setText(new_key_text)
        gui.on_behavior_table_changed(hotkey_item)

        # Verify hotkey updated
        assert gui.behavior_hotkeys[behavior] == new_key

        # Verify legacy list shows new hotkey
        list_items = [
            gui.behavior_list.item(i).text() for i in range(gui.behavior_list.count())
        ]
        assert any(f"{behavior} ({new_key_text})" in item for item in list_items)

        # Test that new hotkey works for annotation
        QTest.keyPress(gui, new_key)
        QTest.qWait(100)
        assert len(gui.timeline.segments) == 1
        assert gui.timeline.segments[0].name == behavior

        QTest.keyRelease(gui, new_key)
        QTest.qWait(100)
        assert gui.timeline.segments[0].end_time is not None

    def test_modify_hotkey_prevents_duplicates(self, gui):
        """Test preventing duplicate hotkey assignment.

        Verifies that assigning an already-used hotkey shows warning
        and reverts to previous value.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Initial state: Immobility has 'I', Rear has 'R'
        assert gui.behavior_hotkeys["Immobile"] == Qt.Key_I
        assert gui.behavior_hotkeys["Rear"] == Qt.Key_R

        # Try to assign 'I' to Rear (already used by Immobility)
        rear_row = gui.behavior_types.index("Rear")

        with patch("annotation_GUI.QMessageBox.warning") as mock_warning:
            # Get the item and change it
            hotkey_item = gui.behavior_table.item(rear_row, 1)
            original_text = hotkey_item.text()
            hotkey_item.setText("I")

            # Trigger the change handler
            gui.on_behavior_table_changed(hotkey_item)

            # Should show warning
            mock_warning.assert_called_once()
            assert "already assigned" in mock_warning.call_args[0][2].lower()

        # Hotkey should remain unchanged
        assert gui.behavior_hotkeys["Rear"] == Qt.Key_R

        # Item should be reverted to original text
        assert hotkey_item.text() == original_text

    def test_modify_behavior_name_prevents_duplicates(self, gui):
        """Test preventing duplicate behavior names.

        Verifies that renaming a behavior to an existing name shows
        warning and reverts the change.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Try to rename Rear to Immobility (duplicate)
        rear_row = gui.behavior_types.index("Rear")

        with patch("annotation_GUI.QMessageBox.warning") as mock_warning:
            # Get the item and change it
            name_item = gui.behavior_table.item(rear_row, 0)
            original_text = name_item.text()
            name_item.setText("Immobile")

            # Trigger the change handler
            gui.on_behavior_table_changed(name_item)

            # Should show warning
            mock_warning.assert_called_once()
            assert "already exists" in mock_warning.call_args[0][2].lower()

        # Behavior should remain unchanged
        assert "Rear" in gui.behavior_types
        assert gui.behavior_types.count("Immobile") == 1

        # Item should be reverted to original text
        assert name_item.text() == original_text

    def test_remove_hotkey_from_table(self, gui):
        """Test removing a hotkey by clearing the cell.

        Verifies that clearing a hotkey cell removes the hotkey mapping.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        behavior = "Immobile"
        assert behavior in gui.behavior_hotkeys

        # Clear the hotkey cell
        hotkey_item = gui.behavior_table.item(0, 1)
        hotkey_item.setText("")
        gui.on_behavior_table_changed(hotkey_item)

        # Verify hotkey was removed
        assert behavior not in gui.behavior_hotkeys

        # Verify legacy list shows no hotkey
        list_items = [
            gui.behavior_list.item(i).text() for i in range(gui.behavior_list.count())
        ]
        # Should just be the behavior name without parentheses
        matching_items = [item for item in list_items if behavior in item]
        assert len(matching_items) > 0
        assert all("(" not in item for item in matching_items)

    def test_invalid_hotkey_rejected(self, gui):
        """Test rejecting invalid hotkey input.

        Verifies that multi-character or invalid hotkeys are rejected
        with appropriate warning message.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        rear_row = gui.behavior_types.index("Rear")
        original_hotkey = gui.behavior_hotkeys["Rear"]

        # Test multi-character input
        with patch("annotation_GUI.QMessageBox.warning") as mock_warning:
            hotkey_item = gui.behavior_table.item(rear_row, 1)
            original_text = hotkey_item.text()
            hotkey_item.setText("ABC")

            gui.on_behavior_table_changed(hotkey_item)

            mock_warning.assert_called_once()
            assert "single letter" in mock_warning.call_args[0][2].lower()

        # Hotkey should remain unchanged
        assert gui.behavior_hotkeys["Rear"] == original_hotkey

        # Item should be reverted
        assert hotkey_item.text() == original_text

    def test_empty_behavior_name_rejected(self, gui):
        """Test rejecting empty behavior name.

        Verifies that empty or whitespace-only behavior names are
        rejected with warning.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        rear_row = gui.behavior_types.index("Rear")

        # Try to set empty name
        with patch("annotation_GUI.QMessageBox.warning") as mock_warning:
            name_item = gui.behavior_table.item(rear_row, 0)
            original_text = name_item.text()
            name_item.setText("")

            gui.on_behavior_table_changed(name_item)

            mock_warning.assert_called_once()
            assert "cannot be empty" in mock_warning.call_args[0][2].lower()

        # Behavior should remain unchanged
        assert "Rear" in gui.behavior_types

        # Item should be reverted
        assert name_item.text() == original_text

    def test_modify_multiple_behaviors_and_export(self, gui, temp_csv):
        """Test modifying multiple behaviors and exporting.

        Verifies that multiple simultaneous modifications to behavior
        names and hotkeys all persist correctly in CSV export.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Create segments for the first three default behaviors
        # (Immobile, Rear, Turn at indices 0, 1, 2)
        seg1 = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        seg2 = BehaviorSegment("Rear", 3.0, 4.0, 90, 120)
        seg3 = BehaviorSegment("Turn", 5.0, 6.0, 150, 180)
        gui.timeline.segments.extend([seg1, seg2, seg3])
        gui.videos[gui.current_video_name]["segments"] = [seg1, seg2, seg3]

        # Modify behavior names at indices 0, 1, 2
        new_names = {0: "Freeze", 1: "RearUp", 2: "SelfGroom"}

        for row, new_name in new_names.items():
            name_item = gui.behavior_table.item(row, 0)
            name_item.setText(new_name)
            gui.on_behavior_table_changed(name_item)

        # Modify all hotkeys
        new_hotkeys = {0: "F", 1: "U", 2: "S"}

        for row, new_key in new_hotkeys.items():
            hotkey_item = gui.behavior_table.item(row, 1)
            hotkey_item.setText(new_key)
            gui.on_behavior_table_changed(hotkey_item)

        # Export to CSV
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        # Verify CSV contains all new names
        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 4  # Header + 3 segments

            exported_behaviors = {row[2] for row in rows[1:]}
            assert exported_behaviors == {"Freeze", "RearUp", "SelfGroom"}

            # Verify old names are not present
            assert "Immobile" not in exported_behaviors
            assert "Rear" not in exported_behaviors
            assert "Turn" not in exported_behaviors

    def test_modify_behavior_updates_all_video_segments(self, gui, tmp_path):
        """Test that modifying a behavior updates segments across all videos.

        Verifies that renaming a behavior updates segments in all loaded
        videos, not just the current one.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            tmp_path: pytest fixture providing temporary directory path.

        Returns:
            None
        """
        # Add segment to first video
        seg1 = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg1)

        # Create and load second video
        video2_path = tmp_path / "video2.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(video2_path), fourcc, 30.0, (640, 480))
        for i in range(150):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            out.write(frame)
        out.release()

        with patch(
            "annotation_GUI.QFileDialog.getOpenFileNames",
            return_value=([str(video2_path)], ""),
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.load_video()

        # Add segment to second video
        gui.video_list.setCurrentRow(1)
        QTest.qWait(100)
        seg2 = BehaviorSegment("Immobile", 3.0, 4.0, 90, 120)
        gui.timeline.segments.append(seg2)

        # Switch back to first video
        gui.video_list.setCurrentRow(0)
        QTest.qWait(100)

        # Modify behavior name
        new_name = "Frozen"
        name_item = gui.behavior_table.item(0, 0)
        name_item.setText(new_name)
        gui.on_behavior_table_changed(name_item)

        # Verify both videos have updated segments
        for video_data in gui.videos.values():
            for seg in video_data["segments"]:
                if seg.start_time in [1.0, 3.0]:  # Our test segments
                    assert seg.name == new_name

    def test_modify_behavior_after_annotation_and_export(self, gui, temp_csv):
        """Test the complete workflow: annotate, modify, export.

        Verifies that annotations made with original behavior names
        export with the modified names after editing the table.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        # Create annotation with original hotkey (I for Immobility)
        QTest.keyPress(gui, Qt.Key_I)
        QTest.qWait(100)
        QTest.keyRelease(gui, Qt.Key_I)
        QTest.qWait(100)

        assert len(gui.timeline.segments) == 1
        assert gui.timeline.segments[0].name == "Immobile"

        # Now modify the behavior name
        new_name = "NotMoving"
        name_item = gui.behavior_table.item(0, 0)
        name_item.setText(new_name)
        gui.on_behavior_table_changed(name_item)

        # Also change the hotkey
        new_key = "N"
        hotkey_item = gui.behavior_table.item(0, 1)
        hotkey_item.setText(new_key)
        gui.on_behavior_table_changed(hotkey_item)

        # Create another annotation with the new hotkey
        QTest.keyPress(gui, Qt.Key_N)
        QTest.qWait(100)
        QTest.keyRelease(gui, Qt.Key_N)
        QTest.qWait(100)

        assert len(gui.timeline.segments) == 2
        assert gui.timeline.segments[0].name == new_name  # First annotation updated
        assert (
            gui.timeline.segments[1].name == new_name
        )  # Second annotation has new name

        # Export and verify
        with patch(
            "annotation_GUI.QFileDialog.getSaveFileName", return_value=(temp_csv, "")
        ):
            with patch("annotation_GUI.QMessageBox.information"):
                gui.export_csv()

        with open(temp_csv, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 3  # Header + 2 segments
            assert all(row[2] == new_name for row in rows[1:])
            assert not any(row[2] == "Immobile" for row in rows[1:])

    def test_modify_behavior_preserves_color_mapping(self, gui):
        """Test that modifying a behavior name preserves its color.

        Verifies that after renaming a behavior, its segments maintain
        the same color on the timeline.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Create segment and record its color
        seg = BehaviorSegment("Immobile", 1.0, 2.0, 30, 60)
        gui.timeline.segments.append(seg)
        original_color = seg.color

        # Modify behavior name
        new_name = "StillBehavior"
        name_item = gui.behavior_table.item(0, 0)
        name_item.setText(new_name)
        gui.on_behavior_table_changed(name_item)

        # Verify segment color unchanged
        assert seg.color == original_color

        # Verify color mapping transferred
        assert new_name in BehaviorSegment._color_map
        assert BehaviorSegment._color_map[new_name] == original_color
        assert "Immobile" not in BehaviorSegment._color_map

    def test_number_keys_as_hotkeys(self, gui):
        """Test that number keys can be assigned as hotkeys.

        Verifies that numeric hotkeys (0-9) work correctly for
        behavior annotation.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Assign number key as hotkey
        hotkey_item = gui.behavior_table.item(0, 1)
        hotkey_item.setText("5")
        gui.on_behavior_table_changed(hotkey_item)

        # Verify hotkey assigned
        assert gui.behavior_hotkeys["Immobile"] == Qt.Key_5

        # Test annotation with number key
        QTest.keyPress(gui, Qt.Key_5)
        QTest.qWait(100)
        assert len(gui.timeline.segments) == 1
        assert gui.timeline.segments[0].name == "Immobile"

        QTest.keyRelease(gui, Qt.Key_5)
        QTest.qWait(100)
        assert gui.timeline.segments[0].end_time is not None

    def test_case_insensitive_hotkey_assignment(self, gui):
        """Test that hotkey assignment is case-insensitive.

        Verifies that lowercase letters are converted to uppercase
        for consistent hotkey handling.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Assign lowercase letter
        hotkey_item = gui.behavior_table.item(0, 1)
        hotkey_item.setText("m")
        gui.on_behavior_table_changed(hotkey_item)

        # Verify stored as uppercase
        assert gui.behavior_hotkeys["Immobile"] == Qt.Key_M

        # Verify display shows uppercase (get fresh item after update)
        updated_item = gui.behavior_table.item(0, 1)
        assert updated_item.text() == "M"

    def test_modify_behavior_with_active_annotation(self, gui):
        """Test modifying behavior while an annotation is in progress.

        Verifies that ongoing annotations are handled correctly when
        the behavior is renamed mid-annotation.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        # Start an annotation
        QTest.keyPress(gui, Qt.Key_I)
        QTest.qWait(100)

        assert len(gui.timeline.segments) == 1
        assert gui.timeline.segments[0].end_time is None
        assert gui.timeline.segments[0].name == "Immobile"

        # Modify behavior name while annotation is ongoing
        new_name = "ActiveImmobility"
        name_item = gui.behavior_table.item(0, 0)
        name_item.setText(new_name)
        gui.on_behavior_table_changed(name_item)

        # Verify ongoing annotation updated
        assert gui.timeline.segments[0].name == new_name

        # The active_hotkeys dict should also be updated
        assert new_name in gui.active_hotkeys
        assert gui.active_hotkeys[new_name] is not False

        # Finish annotation (use the NEW hotkey now since mapping updated)
        QTest.keyRelease(gui, Qt.Key_I)
        QTest.qWait(100)

        # Verify completed annotation has new name
        assert gui.timeline.segments[0].name == new_name
        assert gui.timeline.segments[0].end_time is not None

    def test_behavior_table_synchronizes_with_add_delete(self, gui):
        """Test that table stays synchronized when adding/deleting behaviors.

        Verifies that the table correctly reflects behavior additions
        and deletions, maintaining consistency with the behavior list.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.

        Returns:
            None
        """
        initial_row_count = gui.behavior_table.rowCount()

        # Add a new behavior
        with patch("annotation_GUI.QInputDialog.getText", return_value=("Sniff", True)):
            gui.add_new_behavior()

        # Verify table updated
        assert gui.behavior_table.rowCount() == initial_row_count + 1

        # Check that "Sniff" is in the table
        found = False
        for row in range(gui.behavior_table.rowCount()):
            if gui.behavior_table.item(row, 0).text() == "Sniff":
                found = True
                break
        assert found

        # Delete the behavior
        with patch("annotation_GUI.QInputDialog.getItem", return_value=("Sniff", True)):
            with patch(
                "annotation_GUI.QMessageBox.question", return_value=QMessageBox.Yes
            ):
                gui.delete_behavior()

        # Verify table updated
        assert gui.behavior_table.rowCount() == initial_row_count

        # Check that "Sniff" is no longer in the table
        for row in range(gui.behavior_table.rowCount()):
            assert gui.behavior_table.item(row, 0).text() != "Sniff"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
