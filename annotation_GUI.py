import sys
import cv2
import csv
import os
import random
from typing import Optional, List, Dict, Tuple, Any
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QLabel,
    QSlider,
    QListWidget,
    QListWidgetItem,
    QAction,
    QMessageBox,
    QInputDialog,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QEvent
from PyQt5.QtGui import (
    QImage,
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QKeySequence,
    QPaintEvent,
    QMouseEvent,
    QKeyEvent,
)


# Color palette inspired by seaborn/tableau colors
COLOR_PALETTE = [
    (255, 100, 100),  # Red
    (100, 255, 100),  # Green
    (100, 150, 255),  # Blue
    (255, 179, 71),  # Orange
    (148, 103, 189),  # Purple
    (255, 152, 150),  # Pink
    (140, 86, 75),  # Brown
    (227, 119, 194),  # Magenta
    (127, 127, 127),  # Gray
    (188, 189, 34),  # Olive
    (23, 190, 207),  # Cyan
    (255, 127, 14),  # Dark Orange
    (44, 160, 44),  # Dark Green
    (214, 39, 40),  # Dark Red
    (31, 119, 180),  # Dark Blue
]


class BehaviorSegment:
    """Represents a time segment of a specific behavior in a video.

    This class manages behavior annotations with start/end times and frames,
    and automatically assigns distinct colors to different behaviors.

    Attributes:
        name (str): The name of the behavior.
        start_time (float): Start time in seconds.
        end_time (Optional[float]): End time in seconds, or None if ongoing.
        start_frame (Optional[int]): Start frame number.
        end_frame (Optional[int]): End frame number.
        color (QColor): The color assigned to this behavior type.
        _color_map (Dict[str, QColor]): Class-level mapping of behaviors to colors.
        _used_colors (set): Set of RGB tuples already assigned to behaviors.
    """

    # Class variable to store color mapping
    _color_map: Dict[str, QColor] = {
        "Immobility": QColor(255, 100, 100, 150),
        "Rear": QColor(100, 255, 100, 150),
        "Groom": QColor(100, 150, 255, 150),
    }
    _used_colors: set = set([(255, 100, 100), (100, 255, 100), (100, 150, 255)])

    def __init__(
        self,
        name: str,
        start_time: float,
        end_time: Optional[float] = None,
        start_frame: Optional[int] = None,
        end_frame: Optional[int] = None,
    ) -> None:
        """Initialize a behavior segment.

        Args:
            name: The name of the behavior (e.g., "Immobility", "Groom").
            start_time: Start time of the behavior in seconds.
            end_time: End time of the behavior in seconds. None if still ongoing.
            start_frame: Frame number at start time. None if not yet calculated.
            end_frame: Frame number at end time. None if not yet calculated.

        Returns:
            None
        """
        self.name: str = name
        self.start_time: float = start_time
        self.end_time: Optional[float] = end_time
        self.start_frame: Optional[int] = start_frame
        self.end_frame: Optional[int] = end_frame

        # Get or assign color for this behavior
        if name not in BehaviorSegment._color_map:
            BehaviorSegment._color_map[name] = BehaviorSegment._get_new_color()

        self.color: QColor = BehaviorSegment._color_map[name]

    @classmethod
    def _get_new_color(cls) -> QColor:
        """Get a new distinct color from the palette for a behavior.

        Selects an unused color from COLOR_PALETTE. If all colors are used,
        generates a random bright color.

        Args:
            None

        Returns:
            QColor: A new color with alpha channel set to 150 for transparency.
        """
        # Find unused colors from palette
        available_colors = [c for c in COLOR_PALETTE if c not in cls._used_colors]

        if available_colors:
            # Use a color from the palette
            color_rgb = random.choice(available_colors)
            cls._used_colors.add(color_rgb)
        else:
            # Generate a random bright color if palette is exhausted
            color_rgb = (
                random.randint(100, 255),
                random.randint(100, 255),
                random.randint(100, 255),
            )

        return QColor(color_rgb[0], color_rgb[1], color_rgb[2], 150)

    @classmethod
    def remove_behavior_color(cls, behavior_name: str) -> None:
        """Remove a behavior's color mapping when behavior is deleted.

        Frees up the color for reuse and removes the behavior from the
        color mapping dictionary.

        Args:
            behavior_name: The name of the behavior to remove.

        Returns:
            None
        """
        if behavior_name in cls._color_map:
            color = cls._color_map[behavior_name]
            color_tuple = (color.red(), color.green(), color.blue())
            if color_tuple in cls._used_colors:
                cls._used_colors.discard(color_tuple)
            del cls._color_map[behavior_name]


class TimelineWidget(QWidget):
    """Interactive timeline widget for visualizing and editing behavior segments.

    Displays a horizontal timeline with behavior rows. Users can click to scrub,
    drag segment edges to adjust times, and select segments.

    Signals:
        clicked_pos (float): Emitted when timeline is clicked with time position.
        dragging (float): Emitted while dragging with current time position.
        segment_selected (BehaviorSegment or None): Emitted when segment selection changes.
        segment_modified (BehaviorSegment): Emitted when segment is modified by dragging.

    Attributes:
        duration (float): Total duration of the video in seconds.
        current_time (float): Current playback position in seconds.
        segments (List[BehaviorSegment]): List of behavior segments to display.
        behavior_types (List[str]): List of behavior names to show as rows.
        selected_segment (Optional[BehaviorSegment]): Currently selected segment.
    """

    clicked_pos = pyqtSignal(float)
    dragging = pyqtSignal(float)
    segment_selected = pyqtSignal(object)
    segment_modified = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the timeline widget.

        Args:
            parent: Optional parent widget.

        Returns:
            None
        """
        super().__init__(parent)
        self.duration: float = 1.0
        self.current_time: float = 0.0
        self.segments: List[BehaviorSegment] = []
        self.setMinimumHeight(150)
        self.active_behavior: Optional[str] = None

        # Drag state
        self.is_dragging: bool = False
        self.drag_segment: Optional[BehaviorSegment] = None
        self.drag_edge: Optional[str] = None
        self.EDGE_THRESHOLD: int = 10

        # Scrubbing state
        self.is_scrubbing: bool = False

        # Selection state
        self.selected_segment: Optional[BehaviorSegment] = None

        # Behavior rows
        self.behavior_types: List[str] = ["Immobility", "Rear", "Groom"]
        self.row_height: int = 40

    def update_behavior_types(self, behaviors: List[str]) -> None:
        """Update the list of behavior types displayed as rows.

        Args:
            behaviors: List of behavior names to display.

        Returns:
            None
        """
        self.behavior_types = behaviors
        self.update()

    def get_behavior_row(self, behavior_name: str) -> int:
        """Get the y-coordinate position for a behavior type's row.

        Args:
            behavior_name: Name of the behavior.

        Returns:
            int: Y-coordinate of the top of the behavior's row in pixels.
        """
        if behavior_name in self.behavior_types:
            idx = self.behavior_types.index(behavior_name)
            return 10 + idx * (self.row_height + 5)
        return 10

    def get_segment_at_pos(
        self, x: int, y: int
    ) -> Tuple[Optional[BehaviorSegment], Optional[str]]:
        """Find segment and edge at given mouse position.

        Determines if the position is on a segment's start edge, end edge,
        or body.

        Args:
            x: X-coordinate in pixels.
            y: Y-coordinate in pixels.

        Returns:
            Tuple of (segment, edge) where:
                - segment: BehaviorSegment if found, None otherwise
                - edge: "start", "end", or "body" if segment found, None otherwise
        """
        w = self.width()

        for seg in self.segments:
            row_y = self.get_behavior_row(seg.name)

            if row_y <= y <= row_y + self.row_height:
                x_start = (seg.start_time / self.duration) * w
                x_end = (
                    (seg.end_time / self.duration) * w
                    if seg.end_time
                    else (self.current_time / self.duration) * w
                )

                if abs(x - x_start) < self.EDGE_THRESHOLD:
                    return seg, "start"
                elif seg.end_time and abs(x - x_end) < self.EDGE_THRESHOLD:
                    return seg, "end"
                elif x_start <= x <= x_end:
                    return seg, "body"

        return None, None

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the timeline with behavior rows, segments, and playhead.

        Draws:
            - Dark background
            - Behavior row labels and dividers
            - Behavior segments as colored rectangles
            - Selected segment with yellow border
            - Red vertical playhead line

        Args:
            event: The paint event.

        Returns:
            None
        """
        painter = QPainter(self)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, QColor(40, 40, 40))

        for idx, behavior in enumerate(self.behavior_types):
            y = 10 + idx * (self.row_height + 5)
            painter.setPen(Qt.gray)
            painter.drawLine(0, y + self.row_height, w, y + self.row_height)
            painter.setPen(Qt.white)
            painter.drawText(5, y + 25, behavior)

        for seg in self.segments:
            row_y = self.get_behavior_row(seg.name)
            x_start = (seg.start_time / self.duration) * w
            x_end = (
                (seg.end_time / self.duration) * w
                if seg.end_time
                else (self.current_time / self.duration) * w
            )

            painter.fillRect(
                QRect(int(x_start), row_y, int(x_end - x_start), self.row_height),
                seg.color,
            )

            if seg == self.selected_segment:
                painter.setPen(QPen(QColor(255, 255, 0), 3))
            else:
                painter.setPen(QPen(Qt.white, 1))
            painter.drawRect(int(x_start), row_y, int(x_end - x_start), self.row_height)

        px = (self.current_time / self.duration) * w
        painter.setPen(QPen(Qt.red, 2))
        painter.drawLine(int(px), 0, int(px), h)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for segment selection and timeline scrubbing.

        Determines if user clicked on segment edge (for dragging), segment body
        (for selection), or empty space (for scrubbing).

        Args:
            event: The mouse event containing position and button info.

        Returns:
            None
        """
        seg, edge = self.get_segment_at_pos(event.x(), event.y())

        if seg and edge in ["start", "end"]:
            self.is_dragging = True
            self.drag_segment = seg
            self.drag_edge = edge
            self.selected_segment = seg
            self.segment_selected.emit(seg)
            self.setCursor(Qt.SizeHorCursor)
            self.update()
        elif seg and edge == "body":
            self.selected_segment = seg
            self.segment_selected.emit(seg)
            self.update()
        else:
            self.is_scrubbing = True
            self.selected_segment = None
            self.segment_selected.emit(None)
            pos = event.x() / self.width() * self.duration
            self.clicked_pos.emit(pos)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement for segment edge dragging or timeline scrubbing.

        Updates segment times when dragging edges, ensuring start stays before end.
        Updates cursor appearance when hovering over edges.

        Args:
            event: The mouse event containing current position.

        Returns:
            None
        """
        if self.is_dragging and self.drag_segment:
            new_time = (event.x() / self.width()) * self.duration
            new_time = max(0, min(self.duration, new_time))

            if self.drag_edge == "start":
                if self.drag_segment.end_time:
                    new_time = min(new_time, self.drag_segment.end_time - 0.1)
                self.drag_segment.start_time = new_time
            elif self.drag_edge == "end":
                new_time = max(new_time, self.drag_segment.start_time + 0.1)
                self.drag_segment.end_time = new_time

            self.dragging.emit(new_time)
            self.update()
        elif self.is_scrubbing:
            new_time = (event.x() / self.width()) * self.duration
            new_time = max(0, min(self.duration, new_time))
            self.dragging.emit(new_time)
        else:
            seg, edge = self.get_segment_at_pos(event.x(), event.y())
            if seg and edge in ["start", "end"]:
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release to finalize segment dragging or scrubbing.

        Emits segment_modified signal if a segment was being dragged.
        Resets drag and scrub states.

        Args:
            event: The mouse event.

        Returns:
            None
        """
        # Emit signal if segment was being dragged
        if self.is_dragging and self.drag_segment:
            self.segment_modified.emit(self.drag_segment)

        self.is_dragging = False
        self.is_scrubbing = False
        self.drag_segment = None
        self.drag_edge = None
        self.setCursor(Qt.ArrowCursor)

    def delete_selected_segment(self) -> bool:
        """Delete the currently selected segment from the timeline.

        Returns:
            bool: True if a segment was deleted, False otherwise.
        """
        if self.selected_segment and self.selected_segment in self.segments:
            self.segments.remove(self.selected_segment)
            self.selected_segment = None
            self.segment_selected.emit(None)
            self.update()
            return True
        return False


class AnnotatorGUI(QMainWindow):
    """Main application window for video behavior annotation.

    Provides interface for:
        - Loading multiple videos
        - Annotating behaviors with keyboard hotkeys
        - Visualizing and editing annotations on timeline
        - Exporting annotations to CSV

    Attributes:
        videos (Dict[str, Dict]): Dictionary mapping video names to their data.
        current_video_name (Optional[str]): Name of currently active video.
        cap (Optional[cv2.VideoCapture]): OpenCV video capture object.
        is_playing (bool): Whether video is currently playing.
        behavior_types (List[str]): List of all behavior types.
        behavior_hotkeys (Dict[str, int]): Mapping of behaviors to Qt key codes.
    """

    def __init__(self) -> None:
        """Initialize the annotator GUI application.

        Sets up the main window, initializes state variables, and creates the UI.

        Args:
            None

        Returns:
            None
        """
        super().__init__()
        self.setWindowTitle("Python Behavior Annotator (ChronoViz Style)")
        self.setGeometry(100, 100, 1200, 700)

        # Video management
        self.videos: Dict[str, Dict[str, Any]] = {}
        self.current_video_name: Optional[str] = None

        # State
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_playing: bool = False
        self.current_seg: Optional[BehaviorSegment] = None

        # Hotkey tracking
        self.active_hotkeys: Dict[str, Any] = {}

        # Behavior hotkey mapping
        self.behavior_hotkeys: Dict[str, int] = {
            "Immobility": Qt.Key_I,
            "Rear": Qt.Key_R,
            "Groom": Qt.Key_G,
        }

        # Global behavior types
        self.behavior_types: List[str] = ["Immobility", "Rear", "Groom"]

        # UI Setup
        self.init_ui()

        # Timer for video playback
        self.timer: QTimer = QTimer()
        self.timer.timeout.connect(self.update_frame)

    def init_ui(self) -> None:
        """Initialize and layout all UI components.

        Creates:
            - Left panel with video list
            - Right panel with video display, timeline, and controls
            - Menu bar with File and Behaviors menus
            - Splitter to resize panels

        Args:
            None

        Returns:
            None
        """
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Left panel - Video list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        left_layout.addWidget(QLabel("Videos:"))
        self.video_list = QListWidget()
        self.video_list.currentItemChanged.connect(self.switch_video)
        self.video_list.installEventFilter(self)
        left_layout.addWidget(self.video_list)

        add_video_btn = QPushButton("Add Video")
        add_video_btn.clicked.connect(self.load_video)
        left_layout.addWidget(add_video_btn)

        remove_video_btn = QPushButton("Remove Video")
        remove_video_btn.clicked.connect(self.remove_video)
        left_layout.addWidget(remove_video_btn)

        # Right panel - Main content
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Menu
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        load_act = QAction("Add Video", self)
        load_act.triggered.connect(self.load_video)
        file_menu.addAction(load_act)

        export_act = QAction("Export All to CSV", self)
        export_act.triggered.connect(self.export_csv)
        file_menu.addAction(export_act)

        # Behavior menu
        behavior_menu = menubar.addMenu("Behaviors")

        add_behavior_act = QAction("Add New Behavior", self)
        add_behavior_act.triggered.connect(self.add_new_behavior)
        behavior_menu.addAction(add_behavior_act)

        delete_behavior_act = QAction("Delete Behavior", self)
        delete_behavior_act.triggered.connect(self.delete_behavior)
        behavior_menu.addAction(delete_behavior_act)

        # Video Display
        self.video_label = QLabel("No Video Loaded")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        right_layout.addWidget(self.video_label, 4)

        # Timeline
        self.timeline = TimelineWidget()
        self.timeline.clicked_pos.connect(self.seek_video)
        self.timeline.dragging.connect(self.seek_video)
        self.timeline.segment_selected.connect(self.on_segment_selected)
        self.timeline.segment_modified.connect(self.on_segment_modified)
        self.timeline.behavior_types = self.behavior_types
        self.timeline.installEventFilter(self)
        right_layout.addWidget(self.timeline, 1)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_play = QPushButton("Play/Pause (Space)")
        self.btn_play.clicked.connect(self.toggle_play)

        # Behavior table (new)
        self.behavior_table = QTableWidget()
        self.behavior_table.setColumnCount(2)
        self.behavior_table.setHorizontalHeaderLabels(["Behavior Name", "Hotkey"])
        self.behavior_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.behavior_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.behavior_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.behavior_table.setFixedHeight(150)
        self.behavior_table.itemChanged.connect(self.on_behavior_table_changed)
        self.behavior_table.installEventFilter(self)
        self.update_behavior_table()

        # Keep legacy behavior_list as a list widget for backward compatibility
        self.behavior_list = QListWidget()
        self.behavior_list.installEventFilter(self)
        self.behavior_list.setVisible(False)  # Hide but keep for tests
        self.update_behavior_list()

        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.behavior_table)
        right_layout.addLayout(ctrl_layout)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        layout.addWidget(splitter)

    def update_behavior_table(self) -> None:
        """Update the behavior table with current behaviors and hotkeys.

        Populates the table with editable behavior names and their assigned
        keyboard shortcuts.

        Args:
            None

        Returns:
            None
        """
        # Temporarily disconnect signal to avoid triggering during update
        self.behavior_table.itemChanged.disconnect(self.on_behavior_table_changed)

        self.behavior_table.setRowCount(len(self.behavior_types))

        for idx, behavior in enumerate(self.behavior_types):
            # Behavior name (editable)
            name_item = QTableWidgetItem(behavior)
            self.behavior_table.setItem(idx, 0, name_item)

            # Hotkey (editable)
            if behavior in self.behavior_hotkeys:
                key = self.behavior_hotkeys[behavior]
                key_name = QKeySequence(key).toString()
                hotkey_item = QTableWidgetItem(key_name)
            else:
                hotkey_item = QTableWidgetItem("")

            self.behavior_table.setItem(idx, 1, hotkey_item)

        # Reconnect signal
        self.behavior_table.itemChanged.connect(self.on_behavior_table_changed)

    def on_behavior_table_changed(self, item: QTableWidgetItem) -> None:
        """Handle changes to behavior table cells.

        Updates behavior names or hotkeys when user edits table cells.
        Validates changes and updates all relevant data structures.

        Args:
            item: The table item that was changed.

        Returns:
            None
        """
        row = item.row()
        col = item.column()

        if row >= len(self.behavior_types):
            return

        old_behavior = self.behavior_types[row]

        if col == 0:  # Behavior name changed
            new_name = item.text().strip()

            if not new_name:
                QMessageBox.warning(
                    self, "Invalid Name", "Behavior name cannot be empty."
                )
                self.update_behavior_table()
                return

            if new_name != old_behavior and new_name in self.behavior_types:
                QMessageBox.warning(
                    self, "Duplicate Name", f"Behavior '{new_name}' already exists."
                )
                self.update_behavior_table()
                return

            # Update behavior name everywhere
            self.behavior_types[row] = new_name

            # Update hotkey mapping
            if old_behavior in self.behavior_hotkeys:
                self.behavior_hotkeys[new_name] = self.behavior_hotkeys.pop(
                    old_behavior
                )

            # Update color mapping
            if old_behavior in BehaviorSegment._color_map:
                BehaviorSegment._color_map[new_name] = BehaviorSegment._color_map.pop(
                    old_behavior
                )

            # Update all segments in all videos
            for video_data in self.videos.values():
                for seg in video_data["segments"]:
                    if seg.name == old_behavior:
                        seg.name = new_name

            # Update current timeline segments
            for seg in self.timeline.segments:
                if seg.name == old_behavior:
                    seg.name = new_name

            self.timeline.update_behavior_types(self.behavior_types)
            self.timeline.update()

        elif col == 1:  # Hotkey changed
            new_hotkey_text = item.text().strip().upper()

            if not new_hotkey_text:
                # Remove hotkey
                if old_behavior in self.behavior_hotkeys:
                    del self.behavior_hotkeys[old_behavior]
                return

            # Validate hotkey (single character or number)
            if len(new_hotkey_text) != 1:
                QMessageBox.warning(
                    self, "Invalid Hotkey", "Hotkey must be a single letter or number."
                )
                self.update_behavior_table()
                return

            # Get Qt key code
            key_code = None
            if new_hotkey_text.isalpha():
                key_code = getattr(Qt, f"Key_{new_hotkey_text}", None)
            elif new_hotkey_text.isdigit():
                key_code = getattr(Qt, f"Key_{new_hotkey_text}", None)

            if not key_code:
                QMessageBox.warning(
                    self,
                    "Invalid Hotkey",
                    f"'{new_hotkey_text}' is not a valid hotkey.",
                )
                self.update_behavior_table()
                return

            # Check if hotkey is already in use
            for behavior, existing_key in self.behavior_hotkeys.items():
                if behavior != old_behavior and existing_key == key_code:
                    QMessageBox.warning(
                        self,
                        "Hotkey In Use",
                        f"Hotkey '{new_hotkey_text}' is already assigned to '{behavior}'.",
                    )
                    self.update_behavior_table()
                    return

            # Assign new hotkey
            self.behavior_hotkeys[old_behavior] = key_code

        # Update legacy behavior list
        self.update_behavior_list()

    def update_behavior_list(self) -> None:
        """Update the behavior list widget with current behaviors and hotkeys.

        Refreshes the display to show behavior names with their assigned
        keyboard shortcuts in parentheses.

        Args:
            None

        Returns:
            None
        """
        self.behavior_list.clear()
        for behavior in self.behavior_types:
            if behavior in self.behavior_hotkeys:
                key = self.behavior_hotkeys[behavior]
                key_name = QKeySequence(key).toString()
                self.behavior_list.addItem(f"{behavior} ({key_name})")
            else:
                self.behavior_list.addItem(behavior)

    def add_new_behavior(self) -> None:
        """Add a new behavior type via user input dialog.

        Prompts user for behavior name, assigns a hotkey based on available letters
        or numbers, and updates all relevant UI components. Priority order:
        1. First letter of behavior name
        2. Other letters in behavior name
        3. Number keys 1-9, 0

        Args:
            None

        Returns:
            None
        """
        text, ok = QInputDialog.getText(
            self, "Add New Behavior", "Enter behavior name:"
        )
        if ok and text:
            text = text.strip()
            if not text:
                return

            if text in self.behavior_types:
                QMessageBox.warning(
                    self, "Duplicate", f"Behavior '{text}' already exists."
                )
                return

            self.behavior_types.append(text)

            # Assign a hotkey - try letters first, then numbers
            hotkey_assigned = False

            # Try each letter in the behavior name
            for char in text:
                if char.isalpha():
                    key_name = char.upper()
                    key_code = getattr(Qt, f"Key_{key_name}", None)
                    if key_code and key_code not in self.behavior_hotkeys.values():
                        self.behavior_hotkeys[text] = key_code
                        hotkey_assigned = True
                        break

            # If no letters available, try number keys 1-9, 0
            if not hotkey_assigned:
                for num in [
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "7",
                    "8",
                    "9",
                    "0",
                ]:
                    key_code = getattr(Qt, f"Key_{num}", None)
                    if key_code and key_code not in self.behavior_hotkeys.values():
                        self.behavior_hotkeys[text] = key_code
                        hotkey_assigned = True
                        break

            # If still no hotkey available, notify user
            if not hotkey_assigned:
                QMessageBox.information(
                    self,
                    "No Hotkey Available",
                    f"Could not assign a hotkey to '{text}'. All keys are already used.\n"
                    "You can manually assign a hotkey in the table below.",
                )

            self.timeline.update_behavior_types(self.behavior_types)
            self.update_behavior_table()
            self.update_behavior_list()

            min_height = 20 + len(self.behavior_types) * 45
            self.timeline.setMinimumHeight(min_height)

    def delete_behavior(self) -> None:
        """Delete a behavior type from all videos after confirmation.

        Removes the behavior from all videos' annotations, deletes its color
        mapping, removes its hotkey, and updates the UI.

        Args:
            None

        Returns:
            None
        """
        behaviors = self.behavior_types
        if not behaviors:
            QMessageBox.warning(self, "No Behaviors", "No behaviors to delete.")
            return

        behavior, ok = QInputDialog.getItem(
            self, "Delete Behavior", "Select behavior to delete:", behaviors, 0, False
        )

        if ok and behavior:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete behavior '{behavior}' from ALL videos?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Remove from behavior types
                self.behavior_types.remove(behavior)

                # Remove hotkey
                if behavior in self.behavior_hotkeys:
                    del self.behavior_hotkeys[behavior]

                # Remove color mapping
                BehaviorSegment.remove_behavior_color(behavior)

                # Remove segments from all videos
                for video_data in self.videos.values():
                    video_data["segments"] = [
                        seg for seg in video_data["segments"] if seg.name != behavior
                    ]

                # Remove from current timeline
                self.timeline.segments = [
                    seg for seg in self.timeline.segments if seg.name != behavior
                ]

                self.timeline.update_behavior_types(self.behavior_types)
                self.update_behavior_table()
                self.update_behavior_list()
                self.timeline.update()

                min_height = 20 + len(self.behavior_types) * 45
                self.timeline.setMinimumHeight(max(150, min_height))

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """Filter keyboard events for global hotkey handling.

        Intercepts key presses/releases on child widgets to handle:
            - Space: Play/pause
            - Enter: Start/stop annotation (on behavior table)
            - Delete/Backspace: Delete selected segment
            - Behavior hotkeys: Start/stop behavior annotation

        Args:
            obj: The widget that received the event.
            event: The event to filter.

        Returns:
            bool: True if event was handled, False to pass it on.
        """
        # Handle keyboard events for all child widgets
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space:
                # Don't intercept space in table when editing
                if (
                    obj == self.behavior_table
                    and self.behavior_table.state() == QAbstractItemView.EditingState
                ):
                    return False
                self.toggle_play()
                return True
            elif event.key() in (Qt.Key_Enter, Qt.Key_Return):
                # Handle Enter on behavior_list (for tests)
                if obj == self.behavior_list:
                    self.handle_annotation()
                    return True
                # Handle Enter on behavior_table
                elif (
                    obj == self.behavior_table
                    and self.behavior_table.state() != QAbstractItemView.EditingState
                ):
                    current_row = self.behavior_table.currentRow()
                    if current_row >= 0 and current_row < len(self.behavior_types):
                        behavior = self.behavior_types[current_row]
                        if self.active_hotkeys.get(behavior, False):
                            self.stop_behavior_annotation(behavior)
                        else:
                            self.start_behavior_annotation(behavior)
                    return True
            elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                # Don't intercept in table when editing
                if (
                    obj == self.behavior_table
                    and self.behavior_table.state() == QAbstractItemView.EditingState
                ):
                    return False
                if self.timeline.delete_selected_segment():
                    if self.current_video_name:
                        self.videos[self.current_video_name][
                            "segments"
                        ] = self.timeline.segments.copy()
                return True
            else:
                # Don't intercept behavior hotkeys when editing table
                if (
                    obj == self.behavior_table
                    and self.behavior_table.state() == QAbstractItemView.EditingState
                ):
                    return False

                # Check for behavior hotkeys
                for behavior, key in self.behavior_hotkeys.items():
                    if event.key() == key and not event.isAutoRepeat():
                        self.start_behavior_annotation(behavior)
                        return True
        elif event.type() == QEvent.KeyRelease:
            # Don't intercept when editing table
            if (
                obj == self.behavior_table
                and self.behavior_table.state() == QAbstractItemView.EditingState
            ):
                return False

            # Handle hotkey release
            for behavior, key in self.behavior_hotkeys.items():
                if event.key() == key and not event.isAutoRepeat():
                    if self.active_hotkeys.get(behavior, False):
                        self.stop_behavior_annotation(behavior)
                    return True

        return super().eventFilter(obj, event)

    def load_video(self) -> None:
        """Load one or more video files via file dialog.

        Opens file picker for selecting videos, validates each file,
        extracts metadata (FPS, duration), and adds to video list.
        Shows warning for duplicates or invalid files.

        Args:
            None

        Returns:
            None
        """
        paths, _ = QFileDialog.getOpenFileNames(self, "Open Videos")
        if paths:
            # Track if any videos were successfully added
            added_count = 0
            first_added_name = None

            for path in paths:
                video_name = os.path.basename(path)

                # Check if already loaded
                if video_name in self.videos:
                    QMessageBox.warning(
                        self,
                        "Duplicate",
                        f"Video '{video_name}' is already loaded. Skipping.",
                    )
                    continue

                # Get video properties
                cap = cv2.VideoCapture(path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

                # Validate video
                if fps == 0 or total_frames == 0:
                    QMessageBox.warning(
                        self,
                        "Invalid Video",
                        f"Could not load video '{video_name}'. Skipping.",
                    )
                    cap.release()
                    continue

                duration = total_frames / fps
                cap.release()

                # Store video data
                self.videos[video_name] = {
                    "path": path,
                    "segments": [],
                    "duration": duration,
                    "fps": fps,
                }

                # Add to list
                self.video_list.addItem(video_name)

                # Track first successfully added video
                if first_added_name is None:
                    first_added_name = video_name
                added_count += 1

            # Switch to first added video if any were added
            if added_count > 0 and first_added_name:
                # Find and select the first added video
                items = self.video_list.findItems(first_added_name, Qt.MatchExactly)
                if items:
                    self.video_list.setCurrentItem(items[0])

                # Show success message
                if added_count == 1:
                    QMessageBox.information(self, "Success", f"Added 1 video.")
                else:
                    QMessageBox.information(
                        self, "Success", f"Added {added_count} videos."
                    )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts for main window.

        Processes:
            - Space: Toggle play/pause
            - Enter: Start/stop annotation
            - Delete/Backspace: Delete selected segment
            - Behavior hotkeys: Start behavior annotation

        Args:
            event: The key press event.

        Returns:
            None
        """
        if event.isAutoRepeat():
            return

        if event.key() == Qt.Key_Space:
            self.toggle_play()
        elif event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
            self.handle_annotation()
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.timeline.delete_selected_segment():
                # Update stored segments
                if self.current_video_name:
                    self.videos[self.current_video_name][
                        "segments"
                    ] = self.timeline.segments.copy()
        else:
            # Check for behavior hotkeys
            for behavior, key in self.behavior_hotkeys.items():
                if event.key() == key:
                    self.start_behavior_annotation(behavior)
                    break

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard key releases for ending behavior annotations.

        Detects when a behavior hotkey is released and ends the annotation
        for that behavior.

        Args:
            event: The key release event.

        Returns:
            None
        """
        if event.isAutoRepeat():
            return

        # Check if a behavior hotkey was released
        for behavior, key in self.behavior_hotkeys.items():
            if event.key() == key and self.active_hotkeys.get(behavior, False):
                self.stop_behavior_annotation(behavior)
                break

    def start_behavior_annotation(self, behavior_name: str) -> None:
        """Start annotation for a specific behavior at current video position.

        Creates a new BehaviorSegment with start time and frame at current
        video position. Multiple behaviors can be annotated simultaneously.

        Args:
            behavior_name: Name of the behavior to start annotating.

        Returns:
            None
        """
        if not self.cap:
            return

        if self.active_hotkeys.get(behavior_name, False):
            return

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))

        new_seg = BehaviorSegment(
            behavior_name, current_time, start_frame=current_frame
        )
        self.timeline.segments.append(new_seg)
        self.active_hotkeys[behavior_name] = new_seg
        self.timeline.update()

    def stop_behavior_annotation(self, behavior_name: str) -> None:
        """Stop annotation for a specific behavior at current video position.

        Sets the end time and frame for the active behavior annotation.

        Args:
            behavior_name: Name of the behavior to stop annotating.

        Returns:
            None
        """
        if behavior_name in self.active_hotkeys:
            seg = self.active_hotkeys[behavior_name]
            if seg:
                current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                seg.end_time = current_time
                seg.end_frame = current_frame
                self.active_hotkeys[behavior_name] = False
                self.timeline.update()

                # Update stored segments
                if self.current_video_name:
                    self.videos[self.current_video_name][
                        "segments"
                    ] = self.timeline.segments.copy()

    def handle_annotation(self) -> None:
        """Handle Enter key annotation (legacy two-press method).

        First press starts annotation, second press ends it.
        Uses the currently selected behavior from the behavior list.

        Args:
            None

        Returns:
            None
        """
        if not self.behavior_list.currentItem() or not self.cap:
            return

        behavior_text = self.behavior_list.currentItem().text()
        behavior_name = behavior_text.split(" (")[0]

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))

        if self.current_seg is None:
            self.current_seg = BehaviorSegment(
                behavior_name, current_time, start_frame=current_frame
            )
            self.timeline.segments.append(self.current_seg)
        else:
            self.current_seg.end_time = current_time
            self.current_seg.end_frame = current_frame
            self.current_seg = None
        self.timeline.update()

        # Update stored segments
        if self.current_video_name:
            self.videos[self.current_video_name][
                "segments"
            ] = self.timeline.segments.copy()

    def toggle_play(self) -> None:
        """Toggle video playback between play and pause states.

        Starts or stops the frame update timer based on current play state.
        Timer interval is set according to video FPS.

        Args:
            None

        Returns:
            None
        """
        if not self.cap:
            return

        if self.is_playing:
            self.timer.stop()
        else:
            fps = self.videos[self.current_video_name]["fps"]
            self.timer.start(int(1000 / fps))
        self.is_playing = not self.is_playing

    def update_frame(self) -> None:
        """Read and display the next video frame.

        Reads the current frame from video capture, converts to RGB,
        updates the video label, and updates the timeline playhead.
        Stops playback when video ends.

        Args:
            None

        Returns:
            None
        """
        if not self.cap:
            return

        ret, frame = self.cap.read()
        if ret:
            self.timeline.current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            self.timeline.update()

            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(
                rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888
            )
            self.video_label.setPixmap(
                QPixmap.fromImage(qt_image).scaled(
                    self.video_label.size(), Qt.KeepAspectRatio
                )
            )
        else:
            self.timer.stop()
            self.is_playing = False

    def seek_video(self, time_sec: float) -> None:
        """Seek video to a specific time position.

        Sets the video capture position and updates the displayed frame.

        Args:
            time_sec: Time position in seconds to seek to.

        Returns:
            None
        """
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000.0)
            self.update_frame()

    def export_csv(self) -> None:
        """Export all videos and their annotations to a CSV file.

        Saves current annotations, prompts for file location, and writes
        a CSV with columns: Video, Behavior, Start_Time, End_Time,
        Start_Frame, End_Frame. Shows success message when complete.

        Args:
            None

        Returns:
            None
        """
        # Save current video segments
        if self.current_video_name and self.current_video_name in self.videos:
            self.videos[self.current_video_name][
                "segments"
            ] = self.timeline.segments.copy()

        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Video",
                        "Behavior",
                        "Start_Time",
                        "End_Time",
                        "Start_Frame",
                        "End_Frame",
                    ]
                )

                for video_name, video_data in self.videos.items():
                    for seg in video_data["segments"]:
                        writer.writerow(
                            [
                                video_name,
                                seg.name,
                                seg.start_time,
                                seg.end_time if seg.end_time else "",
                                seg.start_frame if seg.start_frame else "",
                                seg.end_frame if seg.end_frame else "",
                            ]
                        )
            QMessageBox.information(self, "Success", "Exported successfully!")

    def switch_video(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
    ) -> None:
        """Switch to a different video from the video list.

        Saves annotations for the previous video and loads the selected video
        with its associated annotations.

        Args:
            current: The newly selected list item.
            previous: The previously selected list item.

        Returns:
            None
        """
        if current is None:
            return

        # Save current video segments
        if self.current_video_name and self.current_video_name in self.videos:
            self.videos[self.current_video_name][
                "segments"
            ] = self.timeline.segments.copy()

        # Load new video
        video_name = current.text()
        if video_name in self.videos:
            self.current_video_name = video_name
            video_data = self.videos[video_name]

            # Close previous capture
            if self.cap:
                self.cap.release()

            # Open new video
            self.cap = cv2.VideoCapture(video_data["path"])
            self.timeline.duration = video_data["duration"]
            self.timeline.segments = video_data["segments"].copy()
            self.timeline.selected_segment = None
            self.timeline.update()
            self.update_frame()

    def remove_video(self) -> None:
        """Remove the currently selected video and its annotations.

        Prompts user for confirmation before deleting. Releases video capture
        if the removed video is currently active.

        Args:
            None

        Returns:
            None
        """
        current_item = self.video_list.currentItem()
        if current_item:
            video_name = current_item.text()
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete video '{video_name}' and all its annotations?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                if video_name in self.videos:
                    del self.videos[video_name]
                self.video_list.takeItem(self.video_list.row(current_item))
                if self.current_video_name == video_name:
                    self.current_video_name = None
                    if self.cap:
                        self.cap.release()
                        self.cap = None

    def on_segment_selected(self, segment: Optional[BehaviorSegment]) -> None:
        """Handle segment selection event from timeline.

        Callback for when user clicks on a segment in the timeline.
        Currently a placeholder for future functionality.

        Args:
            segment: The selected segment, or None if selection was cleared.

        Returns:
            None
        """
        pass

    def on_segment_modified(self, segment: BehaviorSegment) -> None:
        """Update frame numbers when segment is modified by dragging.

        Recalculates start_frame and end_frame based on the updated
        start_time and end_time after user drags segment edges.

        Args:
            segment: The segment that was modified.

        Returns:
            None
        """
        if not self.cap or not self.current_video_name:
            return

        fps = self.videos[self.current_video_name]["fps"]

        # Recalculate frame numbers based on times
        segment.start_frame = int(segment.start_time * fps)
        if segment.end_time is not None:
            segment.end_frame = int(segment.end_time * fps)

        # Save updated segments
        self.videos[self.current_video_name]["segments"] = self.timeline.segments.copy()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnnotatorGUI()
    window.show()
    sys.exit(app.exec_())
