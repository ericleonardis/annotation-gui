import pytest
import csv
import os
import tempfile
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
        assert seg.name == "Immobility"
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
        assert len(timeline.behavior_types) == 3

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
        row = timeline.get_behavior_row("Immobility")
        assert row == 10  # First behavior at y=10

        row = timeline.get_behavior_row("Rear")
        assert row == 10 + 45  # Second behavior

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

        seg = BehaviorSegment("Immobility", 1.0, 2.0)
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0)
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
        assert window.windowTitle() == "Python Behavior Annotator (ChronoViz Style)"
        assert len(window.videos) == 0
        assert window.current_video_name is None
        assert len(window.behavior_types) == 3

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
        seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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

        with patch("annotation_GUI.QInputDialog.getText", return_value=("Walk", True)):
            gui.add_new_behavior()

        assert len(gui.behavior_types) == initial_count + 1
        assert "Walk" in gui.behavior_types
        assert "Walk" in gui.behavior_hotkeys

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
        seg = BehaviorSegment("Immobility", 1.0, 2.0)
        gui.timeline.segments.append(seg)
        gui.videos[gui.current_video_name]["segments"] = [seg]

        with patch(
            "annotation_GUI.QInputDialog.getItem", return_value=("Immobility", True)
        ):
            with patch(
                "annotation_GUI.QMessageBox.question", return_value=QMessageBox.Yes
            ):
                gui.delete_behavior()

        assert "Immobility" not in gui.behavior_types
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
        assert gui.timeline.segments[0].name == "Immobility"
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0)
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
                "Behavior",
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
            assert rows[1][1] == "Immobility"
            assert float(rows[1][2]) == 1.0
            assert float(rows[1][3]) == 2.0
            assert int(rows[1][4]) == 30
            assert int(rows[1][5]) == 60

    def test_export_multiple_annotations(self, gui, temp_csv):
        """Test exporting multiple annotations.

        Verifies that multiple annotations from same video export correctly.

        Args:
            gui: pytest fixture providing initialized GUI with loaded video.
            temp_csv: pytest fixture providing temporary CSV file path.

        Returns:
            None
        """
        seg1 = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
        seg1 = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
            assert int(rows[1][5]) == 90

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
        seg = BehaviorSegment("Immobility", 1.0, None, 30, None)
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
            assert rows[1][3] == ""  # Empty end time
            assert rows[1][5] == ""  # Empty end frame

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
        seg1 = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
            behaviors = [row[1] for row in rows[1:]]
            assert "Immobility" in behaviors
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
        seg1 = BehaviorSegment("Immobility", 600.0, 900.0, 18000, 27000)  # 10-15 min
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
            assert float(rows[1][2]) == 600.0
            assert float(rows[1][3]) == 900.0
            assert int(rows[1][4]) == 18000
            assert int(rows[1][5]) == 27000

            assert float(rows[3][2]) == 3300.0
            assert int(rows[3][5]) == 105000

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

            exported_behaviors = [row[1] for row in rows[1:]]
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
                seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
        seg = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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

            exported_behaviors = [row[1] for row in rows[1:]]
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
        seg1 = BehaviorSegment("Immobility", 1.0, 2.0, 30, 60)
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
            assert rows[1][1] == "Groom"
            assert rows[2][1] == "Immobility"
            assert rows[3][1] == "Rear"

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
        seg = BehaviorSegment("Immobility", 1.0, 1.001, 30, 30)
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
            assert float(rows[1][2]) == 1.0
            assert float(rows[1][3]) == 1.001


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

        with patch("annotation_GUI.QInputDialog.getText", return_value=("Walk", True)):
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
