import sys
import cv2
import csv
import os
import random
from collections import deque
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

from theme import THEME, apply_theme
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
    QShortcut,
    QMenu,
    QFrame,
    QSizePolicy,
    QProgressDialog,
    QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QEvent
from PyQt5.QtGui import (
    QImage,
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QKeySequence,
    QPaintEvent,
    QMouseEvent,
    QKeyEvent,
    QIcon,
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

    # Class variable to store color mapping (default 5-behavior vocabulary).
    # Vocabulary: Immobile, Rear, Turn, Walk, Groom.
    _color_map: Dict[str, QColor] = {
        "Immobile": QColor(127, 127, 127, 150),
        "Rear": QColor(148, 103, 189, 150),
        "Turn": QColor(255, 179, 71, 150),
        "Walk": QColor(100, 150, 255, 150),
        "Groom": QColor(100, 255, 100, 150),
        # Direction-track labels (rendered in the top strip, not in rows).
        "Left": QColor(79, 140, 255, 180),
        "Right": QColor(255, 120, 80, 180),
        "Straight": QColor(138, 147, 166, 130),
    }
    _used_colors: set = set(
        [
            (127, 127, 127),
            (148, 103, 189),
            (255, 179, 71),
            (100, 150, 255),
            (100, 255, 100),
            (79, 140, 255),
            (255, 120, 80),
            (138, 147, 166),
        ]
    )

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
            name: The name of the behavior (e.g., "Immobile", "Rear") or a
                direction-track label ("Left", "Right", "Straight").
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

    def copy(self) -> "BehaviorSegment":
        """Create a deep copy of this segment.

        Returns:
            BehaviorSegment: A new segment with the same values.
        """
        return BehaviorSegment(
            name=self.name,
            start_time=self.start_time,
            end_time=self.end_time,
            start_frame=self.start_frame,
            end_frame=self.end_frame,
        )


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
    segment_drag_started = pyqtSignal()

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
        self.auto_segments: List[BehaviorSegment] = []
        self.show_auto_overlay: bool = True
        self.setMinimumHeight(150)
        self.active_behavior: Optional[str] = None

        # Drag state
        self.is_dragging: bool = False
        self.drag_segment: Optional[BehaviorSegment] = None
        self.drag_edge: Optional[str] = None
        self.drag_anchor_offset: float = 0.0
        self.EDGE_THRESHOLD: int = 10

        # Scrubbing state
        self.is_scrubbing: bool = False

        # Selection state
        self.selected_segment: Optional[BehaviorSegment] = None

        # Behavior rows (vocabulary: Immobile, Rear, Turn, Walk, Groom)
        self.behavior_types: List[str] = [
            "Immobile",
            "Rear",
            "Turn",
            "Walk",
            "Groom",
        ]
        self.row_height: int = 40
        # Height of the direction-track strip drawn above behavior rows.
        self.direction_strip_height: int = 22
        self.direction_strip_gap: int = 6
        # Direction track segments (Left / Right / Straight).
        self.direction_segments: List[BehaviorSegment] = []

    # ------------------------------------------------------------------
    # Layout geometry helpers
    # ------------------------------------------------------------------

    @property
    def behaviors_origin_y(self) -> int:
        """Y-coordinate of the first behavior row (below the direction strip)."""
        return 10 + self.direction_strip_height + self.direction_strip_gap

    def is_direction_strip_y(self, y: int) -> bool:
        """Whether a y-coordinate falls inside the direction-track strip."""
        return 10 <= y <= 10 + self.direction_strip_height

    def row_from_y(self, y: int) -> int:
        """Map a y-coordinate to a behavior-row index, or -1 if outside rows."""
        rel = y - self.behaviors_origin_y
        if rel < 0:
            return -1
        step = self.row_height + 5
        idx = rel // step
        if 0 <= idx < len(self.behavior_types) and (rel % step) <= self.row_height:
            return int(idx)
        return -1

    def update_behavior_types(self, behaviors: List[str]) -> None:
        """Update the list of behavior types displayed as rows.

        Args:
            behaviors: List of behavior names to display.

        Returns:
            None
        """
        self.behavior_types = behaviors
        # Grow with behavior count so the enclosing QScrollArea can scroll.
        # Includes the direction strip + gap above row 0.
        top = self.behaviors_origin_y
        min_h = top + max(1, len(behaviors)) * (self.row_height + 5) + 10
        self.setMinimumHeight(min_h)
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
            return self.behaviors_origin_y + idx * (self.row_height + 5)
        return self.behaviors_origin_y

    def direction_segment_at(self, x: int) -> Optional[BehaviorSegment]:
        """Find the direction-track segment containing horizontal x."""
        w = self.width()
        if self.duration <= 0 or w <= 0:
            return None
        for seg in self.direction_segments:
            x_start = (seg.start_time / self.duration) * w
            x_end = (
                (seg.end_time / self.duration) * w
                if seg.end_time is not None
                else (self.current_time / self.duration) * w
            )
            if x_start <= x <= x_end:
                return seg
        return None

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
                    if seg.end_time is not None
                    else (self.current_time / self.duration) * w
                )

                if abs(x - x_start) < self.EDGE_THRESHOLD:
                    return seg, "start"
                elif seg.end_time is not None and abs(x - x_end) < self.EDGE_THRESHOLD:
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

        bg_color = QColor(THEME["timeline_bg"])
        divider_color = QColor(THEME["row_divider"])
        text_color = QColor(THEME["text"])
        text_muted = QColor(THEME["text_muted"])
        selection_color = QColor(THEME["selection"])
        playhead_color = QColor(THEME["playhead"])
        row_border_color = QColor(THEME["panel_border"])
        alt_row_bg = QColor(THEME["timeline_row_alt"])

        painter.fillRect(0, 0, w, h, bg_color)

        # Direction-track strip (rendered above behavior rows).
        strip_top = 10
        strip_h = self.direction_strip_height
        painter.fillRect(0, strip_top, w, strip_h, QColor(THEME["panel"]))
        if self.direction_segments and self.duration > 0:
            for seg in self.direction_segments:
                x_start = (seg.start_time / self.duration) * w
                x_end = (
                    (seg.end_time / self.duration) * w
                    if seg.end_time is not None
                    else (self.current_time / self.duration) * w
                )
                seg_w = int(x_end - x_start)
                painter.fillRect(
                    QRect(int(x_start), strip_top, seg_w, strip_h),
                    seg.color,
                )
                # Draw the direction label inside the segment if it fits.
                label = seg.name
                # Use dark text on light fills for legibility.
                painter.setPen(QColor(THEME["text"]))
                fm = painter.fontMetrics()
                text_w = fm.horizontalAdvance(label)
                if seg_w >= text_w + 6:
                    painter.drawText(
                        int(x_start) + 4,
                        strip_top + strip_h - 6,
                        label,
                    )
                elif seg_w >= fm.horizontalAdvance(label[0]) + 4:
                    painter.drawText(
                        int(x_start) + 2,
                        strip_top + strip_h - 6,
                        label[0],
                    )
        painter.setPen(divider_color)
        painter.drawRect(0, strip_top, w - 1, strip_h)
        painter.setPen(text_muted)
        painter.drawText(w - 72, strip_top + strip_h - 6, "direction")

        origin = self.behaviors_origin_y
        for idx, behavior in enumerate(self.behavior_types):
            y = origin + idx * (self.row_height + 5)
            if idx % 2 == 0:
                painter.fillRect(0, y, w, self.row_height, alt_row_bg)
            painter.setPen(divider_color)
            painter.drawLine(0, y + self.row_height, w, y + self.row_height)
            painter.setPen(text_color)
            painter.drawText(8, y + 25, behavior)

        # Auto-label overlay (faded, thinner, under manual segments)
        if self.show_auto_overlay and self.auto_segments:
            overlay_h = max(8, int(self.row_height * 0.35))
            for seg in self.auto_segments:
                row_y = self.get_behavior_row(seg.name)
                x_start = (seg.start_time / self.duration) * w
                x_end = (
                    (seg.end_time / self.duration) * w
                    if seg.end_time is not None
                    else (self.current_time / self.duration) * w
                )
                overlay_color = QColor(seg.color)
                overlay_color.setAlpha(70)
                painter.fillRect(
                    QRect(
                        int(x_start),
                        row_y + self.row_height - overlay_h,
                        int(x_end - x_start),
                        overlay_h,
                    ),
                    overlay_color,
                )
                pen = QPen(QColor(THEME["conflict"]), 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawRect(
                    int(x_start),
                    row_y + self.row_height - overlay_h,
                    int(x_end - x_start),
                    overlay_h,
                )

        for seg in self.segments:
            row_y = self.get_behavior_row(seg.name)
            x_start = (seg.start_time / self.duration) * w
            x_end = (
                (seg.end_time / self.duration) * w
                if seg.end_time is not None
                else (self.current_time / self.duration) * w
            )

            painter.fillRect(
                QRect(int(x_start), row_y, int(x_end - x_start), self.row_height),
                seg.color,
            )

            if seg == self.selected_segment:
                painter.setPen(QPen(selection_color, 3))
            else:
                painter.setPen(QPen(row_border_color, 1))
            painter.drawRect(int(x_start), row_y, int(x_end - x_start), self.row_height)

        px = (self.current_time / self.duration) * w
        painter.setPen(QPen(playhead_color, 2))
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
            self.segment_drag_started.emit()
            self.is_dragging = True
            self.drag_segment = seg
            self.drag_edge = edge
            self.selected_segment = seg
            self.segment_selected.emit(seg)
            self.setCursor(Qt.SizeHorCursor)
            self.update()
        elif seg and edge == "body" and seg.end_time is not None:
            self.segment_drag_started.emit()
            cursor_time = (event.x() / self.width()) * self.duration
            self.is_dragging = True
            self.drag_segment = seg
            self.drag_edge = "body"
            self.drag_anchor_offset = cursor_time - seg.start_time
            self.selected_segment = seg
            self.segment_selected.emit(seg)
            self.setCursor(Qt.SizeAllCursor)
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
            elif self.drag_edge == "body" and self.drag_segment.end_time is not None:
                duration = self.drag_segment.end_time - self.drag_segment.start_time
                new_start = new_time - self.drag_anchor_offset
                new_start = max(0.0, min(self.duration - duration, new_start))
                self.drag_segment.start_time = new_start
                # Vertical drag: change behavior label if cursor has left the
                # current row by more than a 10 px deadzone.
                target_row = self.row_from_y(event.y())
                if (
                    target_row >= 0
                    and target_row < len(self.behavior_types)
                    and self.behavior_types[target_row] != self.drag_segment.name
                ):
                    new_name = self.behavior_types[target_row]
                    self.drag_segment.name = new_name
                    if new_name in BehaviorSegment._color_map:
                        self.drag_segment.color = BehaviorSegment._color_map[new_name]
                self.drag_segment.end_time = new_start + duration

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
            elif seg and edge == "body" and seg.end_time is not None:
                self.setCursor(Qt.SizeAllCursor)
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
        self.setWindowTitle("Python Behavior Annotator")
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

        # Undo/redo snapshot stacks (capped)
        self._undo_stack: deque = deque(maxlen=100)
        self._redo_stack: deque = deque(maxlen=100)
        self._undo_suspended: bool = False

        # Behavior hotkey mapping (vocabulary: Immobile, Rear, Turn, Walk, Groom)
        self.behavior_hotkeys: Dict[str, int] = {
            "Immobile": Qt.Key_I,
            "Rear": Qt.Key_R,
            "Turn": Qt.Key_T,
            "Walk": Qt.Key_W,
            "Groom": Qt.Key_G,
        }

        # Global behavior types
        self.behavior_types: List[str] = [
            "Immobile",
            "Rear",
            "Turn",
            "Walk",
            "Groom",
        ]

        # UI Setup
        self.init_ui()

        # Timer for video playback
        self.timer: QTimer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        # Auto-load sample videos + labels if present (skip in test env)
        if not os.environ.get("ANNOTATION_GUI_NO_AUTOLOAD"):
            self._autoload_sample_dataset()

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

        import_act = QAction("Import from CSV", self)
        import_act.triggered.connect(self.import_csv)
        file_menu.addAction(import_act)

        # Behavior menu
        behavior_menu = menubar.addMenu("Behaviors")

        add_behavior_act = QAction("Add New Behavior", self)
        add_behavior_act.triggered.connect(self.add_new_behavior)
        behavior_menu.addAction(add_behavior_act)

        delete_behavior_act = QAction("Delete Behavior", self)
        delete_behavior_act.triggered.connect(self.delete_behavior)
        behavior_menu.addAction(delete_behavior_act)

        # Auto-label menu
        auto_menu = menubar.addMenu("Auto-label")

        auto_current_act = QAction("Auto-label Current Clip", self)
        auto_current_act.triggered.connect(self.auto_label_current)
        auto_menu.addAction(auto_current_act)

        auto_all_act = QAction("Auto-label All Unlabeled Clips", self)
        auto_all_act.triggered.connect(self.auto_label_all_unlabeled)
        auto_menu.addAction(auto_all_act)

        auto_menu.addSeparator()

        auto_dir_current_act = QAction("Auto-directionality (current clip)", self)
        auto_dir_current_act.triggered.connect(self.auto_direction_current)
        auto_menu.addAction(auto_dir_current_act)

        auto_dir_all_act = QAction("Auto-directionality (all clips)", self)
        auto_dir_all_act.triggered.connect(self.auto_direction_all)
        auto_menu.addAction(auto_dir_all_act)

        auto_menu.addSeparator()

        toggle_overlay_act = QAction("Toggle Auto Overlay", self)
        toggle_overlay_act.triggered.connect(self.toggle_auto_overlay)
        auto_menu.addAction(toggle_overlay_act)

        # Video Display — must ignore its pixmap's size hint so the label
        # does not grow to fit each frame (otherwise the widget expands every
        # time setPixmap is called with a larger pixmap than the last).
        self.video_label = QLabel("No Video Loaded")
        self.video_label.setObjectName("video_display")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(1, 1)
        self.video_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        right_layout.addWidget(self.video_label, 4)

        # Timeline
        self.timeline = TimelineWidget()
        self.timeline.clicked_pos.connect(self.seek_video)
        self.timeline.dragging.connect(self.seek_video)
        self.timeline.segment_selected.connect(self.on_segment_selected)
        self.timeline.segment_modified.connect(self.on_segment_modified)
        self.timeline.segment_drag_started.connect(self._push_undo)
        self.timeline.behavior_types = self.behavior_types
        self.timeline.update_behavior_types(self.behavior_types)
        self.timeline.installEventFilter(self)
        self.timeline.setContextMenuPolicy(Qt.CustomContextMenu)
        self.timeline.customContextMenuRequested.connect(
            self._on_timeline_context_menu
        )
        # Wrap the timeline in a vertical scroll area so rows beyond the
        # visible region remain reachable when many behaviors are present.
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.timeline_scroll.setWidget(self.timeline)
        right_layout.addWidget(self.timeline_scroll, 1)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_play = QPushButton("Play/Pause (Space)")
        self.btn_play.clicked.connect(self.toggle_play)

        self.btn_auto_label = QPushButton("Auto-label Clip")
        self.btn_auto_label.setObjectName("primary")
        self.btn_auto_label.clicked.connect(self.auto_label_current)

        self.btn_auto_direction = QPushButton("Auto-directionality")
        self.btn_auto_direction.setToolTip(
            "Infer Left / Right / Straight segments from qpos yaw for this clip"
        )
        self.btn_auto_direction.clicked.connect(self.auto_direction_current)

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
        self.behavior_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.behavior_table.setFixedHeight(150)
        self.behavior_table.itemChanged.connect(self.on_behavior_table_changed)
        self.behavior_table.installEventFilter(self)
        self.update_behavior_table()

        # Keep legacy behavior_list as a list widget for backward compatibility
        self.behavior_list = QListWidget()
        self.behavior_list.installEventFilter(self)
        self.behavior_list.setVisible(False)  # Hide but keep for tests
        self.update_behavior_list()

        btn_col = QVBoxLayout()
        btn_col.addWidget(self.btn_play)
        btn_col.addWidget(self.btn_auto_label)
        btn_col.addWidget(self.btn_auto_direction)
        btn_col.addStretch(1)
        ctrl_layout.addLayout(btn_col)
        ctrl_layout.addWidget(self.behavior_table)
        right_layout.addLayout(ctrl_layout)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        layout.addWidget(splitter)

        # Undo / Redo shortcuts (Ctrl+Z / Ctrl+Shift+Z — Cmd on macOS)
        undo_sc = QShortcut(QKeySequence.Undo, self)
        undo_sc.setContext(Qt.ApplicationShortcut)
        undo_sc.activated.connect(self.undo)

        redo_sc = QShortcut(QKeySequence.Redo, self)
        redo_sc.setContext(Qt.ApplicationShortcut)
        redo_sc.activated.connect(self.redo)

        # Auto-pipeline shortcuts (Ctrl/Cmd-L = auto-label, Ctrl/Cmd-D = auto-direction)
        label_sc = QShortcut(QKeySequence("Ctrl+L"), self)
        label_sc.setContext(Qt.ApplicationShortcut)
        label_sc.activated.connect(self.auto_label_current)

        dir_sc = QShortcut(QKeySequence("Ctrl+D"), self)
        dir_sc.setContext(Qt.ApplicationShortcut)
        dir_sc.activated.connect(self.auto_direction_current)


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

        self._push_undo()

        if col == 0:  # Behavior name changed
            new_name = item.text().strip()

            if not new_name:
                QMessageBox.warning(
                    self, "Invalid Name", "Behavior name cannot be empty."
                )
                # Revert to original name without recreating table
                self.behavior_table.blockSignals(True)
                item.setText(old_behavior)
                self.behavior_table.blockSignals(False)
                return

            if new_name != old_behavior and new_name in self.behavior_types:
                QMessageBox.warning(
                    self, "Duplicate Name", f"Behavior '{new_name}' already exists."
                )
                # Revert to original name without recreating table
                self.behavior_table.blockSignals(True)
                item.setText(old_behavior)
                self.behavior_table.blockSignals(False)
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

            # Update active hotkeys tracking
            if old_behavior in self.active_hotkeys:
                self.active_hotkeys[new_name] = self.active_hotkeys.pop(old_behavior)

            self.timeline.update_behavior_types(self.behavior_types)
            self.timeline.update()

        elif col == 1:  # Hotkey changed
            new_hotkey_text = item.text().strip().upper()

            if not new_hotkey_text:
                # Remove hotkey
                if old_behavior in self.behavior_hotkeys:
                    del self.behavior_hotkeys[old_behavior]
                # Update legacy list after removing hotkey
                self.update_behavior_list()
                return

            # Validate hotkey (single character or number)
            if len(new_hotkey_text) != 1:
                QMessageBox.warning(
                    self, "Invalid Hotkey", "Hotkey must be a single letter or number."
                )
                # Revert to original hotkey without recreating table
                self.behavior_table.blockSignals(True)
                if old_behavior in self.behavior_hotkeys:
                    old_key = self.behavior_hotkeys[old_behavior]
                    old_key_text = QKeySequence(old_key).toString()
                    item.setText(old_key_text)
                else:
                    item.setText("")
                self.behavior_table.blockSignals(False)
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
                # Revert to original hotkey without recreating table
                self.behavior_table.blockSignals(True)
                if old_behavior in self.behavior_hotkeys:
                    old_key = self.behavior_hotkeys[old_behavior]
                    old_key_text = QKeySequence(old_key).toString()
                    item.setText(old_key_text)
                else:
                    item.setText("")
                self.behavior_table.blockSignals(False)
                return

            # Check if hotkey is already in use
            for behavior, existing_key in self.behavior_hotkeys.items():
                if behavior != old_behavior and existing_key == key_code:
                    QMessageBox.warning(
                        self,
                        "Hotkey In Use",
                        f"Hotkey '{new_hotkey_text}' is already assigned to '{behavior}'.",
                    )
                    # Revert to original hotkey without recreating table
                    self.behavior_table.blockSignals(True)
                    if old_behavior in self.behavior_hotkeys:
                        old_key = self.behavior_hotkeys[old_behavior]
                        old_key_text = QKeySequence(old_key).toString()
                        item.setText(old_key_text)
                    else:
                        item.setText("")
                    self.behavior_table.blockSignals(False)
                    return

            # Assign new hotkey
            self.behavior_hotkeys[old_behavior] = key_code

            # Update the displayed text to uppercase (already done above)
            self.behavior_table.blockSignals(True)
            item.setText(new_hotkey_text)
            self.behavior_table.blockSignals(False)

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

            self._push_undo()

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
                self._push_undo()

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
                if self.timeline.selected_segment is not None:
                    self._push_undo()
                if self.timeline.delete_selected_segment():
                    if self.current_video_name:
                        self.videos[self.current_video_name][
                            "segments"
                        ] = self._deep_copy_segments(self.timeline.segments)
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
                    "direction_segments": [],
                    "auto_segments": [],
                    "has_conflict": False,
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
            if self.timeline.selected_segment is not None:
                self._push_undo()
            if self.timeline.delete_selected_segment():
                # Update stored segments (deep copy)
                if self.current_video_name:
                    self.videos[self.current_video_name][
                        "segments"
                    ] = self._deep_copy_segments(self.timeline.segments)
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

        self._push_undo()

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

                # Update stored segments (deep copy)
                if self.current_video_name:
                    self.videos[self.current_video_name][
                        "segments"
                    ] = self._deep_copy_segments(self.timeline.segments)

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
            self._push_undo()
            self.current_seg = BehaviorSegment(
                behavior_name, current_time, start_frame=current_frame
            )
            self.timeline.segments.append(self.current_seg)
        else:
            self.current_seg.end_time = current_time
            self.current_seg.end_frame = current_frame
            self.current_seg = None
        self.timeline.update()

        # Update stored segments (deep copy)
        if self.current_video_name:
            self.videos[self.current_video_name][
                "segments"
            ] = self._deep_copy_segments(self.timeline.segments)

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
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
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
        # Save current video segments (deep copy)
        if self.current_video_name and self.current_video_name in self.videos:
            self.videos[self.current_video_name][
                "segments"
            ] = self._deep_copy_segments(self.timeline.segments)

        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Video",
                        "Track",
                        "Label",
                        "Start_Time",
                        "End_Time",
                        "Start_Frame",
                        "End_Frame",
                    ]
                )

                for video_name, video_data in self.videos.items():
                    for seg in video_data.get("segments", []):
                        writer.writerow(
                            [
                                video_name,
                                "behavior",
                                seg.name,
                                seg.start_time,
                                seg.end_time if seg.end_time is not None else "",
                                seg.start_frame if seg.start_frame is not None else "",
                                seg.end_frame if seg.end_frame is not None else "",
                            ]
                        )
                    for seg in video_data.get("direction_segments", []):
                        writer.writerow(
                            [
                                video_name,
                                "direction",
                                seg.name,
                                seg.start_time,
                                seg.end_time if seg.end_time is not None else "",
                                seg.start_frame if seg.start_frame is not None else "",
                                seg.end_frame if seg.end_frame is not None else "",
                            ]
                        )
            QMessageBox.information(self, "Success", "Exported successfully!")

    def import_csv(self) -> None:
        """Import annotations from a CSV file and load associated videos.

        Reads a CSV file exported by this application, prompts user to locate
        video files if not found, adds any new behaviors, and recreates all
        annotation segments.

        The CSV format expected:
            Video, Behavior, Start_Time, End_Time, Start_Frame, End_Frame

        Args:
            None

        Returns:
            None
        """
        # Open file dialog to select CSV
        csv_path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv)"
        )
        if not csv_path:
            return

        self._push_undo()

        csv_dir = os.path.dirname(csv_path)

        # Read and normalize rows into the new-schema shape:
        #   {Video, Track, Label, Start_Time, End_Time, Start_Frame, End_Frame}
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = set(reader.fieldnames or [])
                raw_rows: List[Dict[str, str]] = list(reader)

            if not {"Video", "Start_Time", "End_Time"}.issubset(fieldnames):
                QMessageBox.warning(
                    self,
                    "Invalid CSV",
                    "CSV file is missing required columns.\n"
                    "Expected at least: Video, Start_Time, End_Time.",
                )
                return

            raw_rows = self._normalize_import_rows(raw_rows, fieldnames)

            annotations_by_video: Dict[str, List[Dict[str, Any]]] = {}
            csv_behaviors: set = set()

            for row in raw_rows:
                video_name = row["Video"]
                annotations_by_video.setdefault(video_name, []).append(row)
                if row["Track"] == "behavior":
                    csv_behaviors.add(row["Label"])

        except Exception as e:
            QMessageBox.warning(
                self, "Error Reading CSV", f"Failed to read CSV file:\n{str(e)}"
            )
            return

        if not annotations_by_video:
            QMessageBox.information(
                self, "Empty CSV", "The CSV file contains no annotations."
            )
            return

        # Replace default behaviors with CSV behaviors
        self.behavior_types.clear()
        self.behavior_hotkeys.clear()

        for behavior in csv_behaviors:
            self.behavior_types.append(behavior)

            # Try to assign a hotkey
            hotkey_assigned = False
            for char in behavior:
                if char.isalpha():
                    key_name = char.upper()
                    key_code = getattr(Qt, f"Key_{key_name}", None)
                    if key_code and key_code not in self.behavior_hotkeys.values():
                        self.behavior_hotkeys[behavior] = key_code
                        hotkey_assigned = True
                        break

            if not hotkey_assigned:
                for num in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]:
                    key_code = getattr(Qt, f"Key_{num}", None)
                    if key_code and key_code not in self.behavior_hotkeys.values():
                        self.behavior_hotkeys[behavior] = key_code
                        break

        # Update behavior UI
        self.timeline.update_behavior_types(self.behavior_types)
        self.update_behavior_table()
        self.update_behavior_list()

        # Process each video
        videos_loaded = 0
        videos_skipped = 0
        video_path_cache: Dict[str, str] = {}  # Cache for located video paths

        for video_name, annotations in annotations_by_video.items():
            video_path = None

            # Check if video is already loaded
            if video_name in self.videos:
                # Video already loaded, just add/merge segments
                video_path = self.videos[video_name]["path"]
            else:
                # Try to find video in CSV directory first
                potential_path = os.path.join(csv_dir, video_name)
                if os.path.isfile(potential_path):
                    video_path = potential_path
                else:
                    # Prompt user to locate the video
                    reply = QMessageBox.question(
                        self,
                        "Locate Video",
                        f"Video '{video_name}' not found in CSV directory.\n"
                        "Would you like to locate it manually?",
                        QMessageBox.Yes | QMessageBox.No,
                    )

                    if reply == QMessageBox.Yes:
                        located_path, _ = QFileDialog.getOpenFileName(
                            self,
                            f"Locate Video: {video_name}",
                            csv_dir,
                            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv);;All Files (*)",
                        )
                        if located_path:
                            video_path = located_path
                        else:
                            videos_skipped += 1
                            continue
                    else:
                        videos_skipped += 1
                        continue

            # Load video if not already loaded
            if video_name not in self.videos:
                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)

                if fps == 0 or total_frames == 0:
                    QMessageBox.warning(
                        self,
                        "Invalid Video",
                        f"Could not load video '{video_name}'. Skipping.",
                    )
                    cap.release()
                    videos_skipped += 1
                    continue

                duration = total_frames / fps
                cap.release()

                self.videos[video_name] = {
                    "path": video_path,
                    "segments": [],
                    "direction_segments": [],
                    "auto_segments": [],
                    "has_conflict": False,
                    "duration": duration,
                    "fps": fps,
                }

                self.video_list.addItem(video_name)

            # Build behavior + direction segments from annotations
            fps = self.videos[video_name]["fps"]
            behavior_segs: List[BehaviorSegment] = []
            direction_segs: List[BehaviorSegment] = []

            for ann in annotations:
                try:
                    start_time_str = str(ann.get("Start_Time", "")).strip()
                    start_time = float(start_time_str) if start_time_str else 0.0

                    end_time_str = str(ann.get("End_Time", "")).strip()
                    end_time = float(end_time_str) if end_time_str else None

                    start_frame_str = str(ann.get("Start_Frame", "")).strip()
                    start_frame = (
                        int(start_frame_str)
                        if start_frame_str
                        else int(start_time * fps)
                    )

                    end_frame_str = str(ann.get("End_Frame", "")).strip()
                    end_frame = (
                        int(end_frame_str)
                        if end_frame_str
                        else (int(end_time * fps) if end_time is not None else None)
                    )

                    seg = BehaviorSegment(
                        name=ann["Label"],
                        start_time=start_time,
                        end_time=end_time,
                        start_frame=start_frame,
                        end_frame=end_frame,
                    )
                    if ann.get("Track", "behavior") == "direction":
                        direction_segs.append(seg)
                    else:
                        behavior_segs.append(seg)

                except (ValueError, KeyError):
                    continue

            self.videos[video_name]["segments"] = behavior_segs
            self.videos[video_name]["direction_segments"] = direction_segs

            incomplete_count = sum(
                1 for seg in behavior_segs if seg.end_time is None
            )
            if incomplete_count > 0 and incomplete_count == len(behavior_segs):
                QMessageBox.warning(
                    self,
                    "Incomplete Annotations",
                    f"Video '{video_name}': All {incomplete_count} annotations have no end time.\n"
                    "This may indicate the annotations were not completed before export.",
                )

            videos_loaded += 1

        # Update timeline height for new behaviors
        min_height = 20 + len(self.behavior_types) * 45
        self.timeline.setMinimumHeight(max(150, min_height))

        # Switch to first loaded video if no video is currently selected
        if self.video_list.count() > 0 and self.current_video_name is None:
            self.video_list.setCurrentRow(0)

        # Refresh current video's timeline if it was updated
        if self.current_video_name and self.current_video_name in self.videos:
            self._stop_all_active_annotations()

            self.timeline.duration = self.videos[self.current_video_name]["duration"]
            self.timeline.current_time = 0.0
            self.timeline.segments = self._deep_copy_segments(
                self.videos[self.current_video_name].get("segments", [])
            )
            self.timeline.direction_segments = self._deep_copy_segments(
                self.videos[self.current_video_name].get("direction_segments", [])
            )

            self.active_hotkeys = {behavior: False for behavior in self.behavior_types}

            self.timeline.update()

        # Show summary
        message = f"Import complete!\n\nVideos loaded: {videos_loaded}"
        if videos_skipped > 0:
            message += f"\nVideos skipped: {videos_skipped}"
        if csv_behaviors:
            message += f"\nBehaviors loaded: {', '.join(csv_behaviors)}"

        QMessageBox.information(self, "Import Complete", message)

    # Vocabulary rename map for legacy CSVs (and legacy stored state).
    _LEGACY_RENAME = {
        "Immobility": "Immobile",
        "Walking": "Walk",
        "Grooming": "Groom",
        "Orienting": "Turn",
        "Supported Rear": "Rear",
        "Unsupported Rear": "Rear",
    }

    def _normalize_import_rows(
        self, rows: List[Dict[str, str]], fieldnames: set
    ) -> List[Dict[str, str]]:
        """Coerce legacy/current import CSVs into the new Track/Label schema.

        Supports three input shapes:
          - New: columns include Track + Label (pass through).
          - Old (Direction-flag era): Video,Behavior,Direction,Start_Time,...
            Behavior row becomes Track=behavior with renamed Label. Any row
            whose Direction in {left,right} also emits a separate
            Track=direction row covering the same time span.
          - Legacy (6-col): Video,Behavior,Start_Time,... — Left/Right Turn
            behaviors become direction rows; everything else becomes a
            renamed behavior row. No segment splitting.
        """
        has_track = "Track" in fieldnames
        has_direction_col = "Direction" in fieldnames
        has_label = "Label" in fieldnames

        out: List[Dict[str, str]] = []
        for r in rows:
            video = r.get("Video", "")
            ts = r.get("Start_Time", "")
            te = r.get("End_Time", "")
            fs = r.get("Start_Frame", "")
            fe = r.get("End_Frame", "")

            if has_track:
                label = r.get("Label", "") if has_label else r.get("Behavior", "")
                track = r.get("Track", "behavior") or "behavior"
                label = self._LEGACY_RENAME.get(label, label)
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
                continue

            beh = (r.get("Behavior") or "").strip()

            if beh in ("Left Turn", "Right Turn"):
                out.append(
                    {
                        "Video": video,
                        "Track": "direction",
                        "Label": "Left" if beh == "Left Turn" else "Right",
                        "Start_Time": ts,
                        "End_Time": te,
                        "Start_Frame": fs,
                        "End_Frame": fe,
                    }
                )
                continue

            renamed = self._LEGACY_RENAME.get(beh, beh)
            out.append(
                {
                    "Video": video,
                    "Track": "behavior",
                    "Label": renamed,
                    "Start_Time": ts,
                    "End_Time": te,
                    "Start_Frame": fs,
                    "End_Frame": fe,
                }
            )

            if has_direction_col:
                dir_val = (r.get("Direction") or "").strip().lower()
                if dir_val in ("left", "right"):
                    out.append(
                        {
                            "Video": video,
                            "Track": "direction",
                            "Label": "Left" if dir_val == "left" else "Right",
                            "Start_Time": ts,
                            "End_Time": te,
                            "Start_Frame": fs,
                            "End_Frame": fe,
                        }
                    )

        return out

    def _deep_copy_segments(
        self, segments: List[BehaviorSegment]
    ) -> List[BehaviorSegment]:
        """Create deep copies of all segments in a list.

        Args:
            segments: List of segments to copy.

        Returns:
            List[BehaviorSegment]: New list with copied segment objects.
        """
        return [seg.copy() for seg in segments]

    def _snapshot(self) -> Dict[str, Any]:
        """Capture a deep-copied snapshot of annotation state for undo.

        Returns:
            Dict with segments-per-video (deep copied), current video name,
            behavior_types and behavior_hotkeys (shallow copied).
        """
        return {
            "segments_by_video": {
                name: self._deep_copy_segments(data.get("segments", []))
                for name, data in self.videos.items()
            },
            "direction_segments_by_video": {
                name: self._deep_copy_segments(data.get("direction_segments", []))
                for name, data in self.videos.items()
            },
            "auto_segments_by_video": {
                name: self._deep_copy_segments(data.get("auto_segments", []))
                for name, data in self.videos.items()
            },
            "current_video_name": self.current_video_name,
            "behavior_types": list(self.behavior_types),
            "behavior_hotkeys": dict(self.behavior_hotkeys),
            "timeline_segments": self._deep_copy_segments(self.timeline.segments),
            "timeline_direction_segments": self._deep_copy_segments(
                self.timeline.direction_segments
            ),
        }

    def _push_undo(self) -> None:
        """Push a snapshot to the undo stack and clear redo.

        No-op when undo recording is suspended (during undo/redo restoration)
        or when there is no active video.
        """
        if self._undo_suspended:
            return
        self._undo_stack.append(self._snapshot())
        self._redo_stack.clear()

    def _restore(self, snap: Dict[str, Any]) -> None:
        """Restore annotation state from a snapshot."""
        self._undo_suspended = True
        try:
            for name, segs in snap["segments_by_video"].items():
                if name in self.videos:
                    self.videos[name]["segments"] = [s.copy() for s in segs]
            for name, segs in snap.get("direction_segments_by_video", {}).items():
                if name in self.videos:
                    self.videos[name]["direction_segments"] = [s.copy() for s in segs]
            for name, segs in snap["auto_segments_by_video"].items():
                if name in self.videos:
                    self.videos[name]["auto_segments"] = [s.copy() for s in segs]
                    self.videos[name]["has_conflict"] = bool(segs) and bool(
                        self.videos[name].get("segments")
                    )
            self.behavior_types = list(snap["behavior_types"])
            self.behavior_hotkeys = dict(snap["behavior_hotkeys"])

            target = snap["current_video_name"]
            if target and target in self.videos:
                self.current_video_name = target
                self.timeline.segments = [s.copy() for s in snap["timeline_segments"]]
                self.timeline.direction_segments = [
                    s.copy()
                    for s in snap.get("timeline_direction_segments", [])
                ]
                self.timeline.auto_segments = [
                    s.copy() for s in self.videos[target].get("auto_segments", [])
                ]
                self.timeline.duration = self.videos[target].get("duration", 1.0)

            self.timeline.update_behavior_types(self.behavior_types)
            self.update_behavior_table()
            self.update_behavior_list()
            self._refresh_video_list_conflict_flags()
            self.timeline.update()
        finally:
            self._undo_suspended = False

    def undo(self) -> None:
        """Undo the last recorded mutation."""
        if not self._undo_stack:
            return
        current = self._snapshot()
        snap = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore(snap)

    def redo(self) -> None:
        """Redo the last undone mutation."""
        if not self._redo_stack:
            return
        current = self._snapshot()
        snap = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore(snap)

    def _refresh_video_list_conflict_flags(self) -> None:
        """Refresh the '!' prefix on video list items that have unresolved auto/manual conflicts."""
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            name = item.text().lstrip("! ").strip()
            has_conflict = self.videos.get(name, {}).get("has_conflict", False)
            item.setText(f"! {name}" if has_conflict else name)

    def _stop_all_active_annotations(self) -> None:
        """Stop all active annotations by setting their end time.

        This should be called before switching videos to ensure no annotations
        are left in an incomplete state with end_time=None.

        Args:
            None

        Returns:
            None
        """
        if not self.cap:
            return

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))

        for behavior_name, seg in list(self.active_hotkeys.items()):
            if seg and seg is not False:
                # Set end time for the active segment
                seg.end_time = current_time
                seg.end_frame = current_frame
                self.active_hotkeys[behavior_name] = False

        # Also handle legacy current_seg if it exists
        if self.current_seg is not None:
            self.current_seg.end_time = current_time
            self.current_seg.end_frame = current_frame
            self.current_seg = None

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

        # Stop any active annotations before switching
        self._stop_all_active_annotations()

        # Save current video segments (deep copy to isolate from timeline)
        if self.current_video_name and self.current_video_name in self.videos:
            self.videos[self.current_video_name][
                "segments"
            ] = self._deep_copy_segments(self.timeline.segments)
            self.videos[self.current_video_name][
                "auto_segments"
            ] = self._deep_copy_segments(self.timeline.auto_segments)
            self.videos[self.current_video_name][
                "direction_segments"
            ] = self._deep_copy_segments(self.timeline.direction_segments)

        # Load new video — strip any leading conflict "! " marker
        video_name = current.text().lstrip("! ").strip()
        if video_name in self.videos:
            self._ensure_video_metadata(video_name)
            self.current_video_name = video_name
            video_data = self.videos[video_name]

            # Close previous capture
            if self.cap:
                self.cap.release()

            # Open new video
            self.cap = cv2.VideoCapture(video_data["path"])
            self.timeline.duration = video_data["duration"]

            # Reset current_time to 0 before loading segments
            self.timeline.current_time = 0.0

            # Deep copy segments to isolate timeline from stored data
            self.timeline.segments = self._deep_copy_segments(video_data.get("segments", []))
            self.timeline.auto_segments = self._deep_copy_segments(
                video_data.get("auto_segments", [])
            )
            self.timeline.direction_segments = self._deep_copy_segments(
                video_data.get("direction_segments", [])
            )
            self.timeline.selected_segment = None

            # Clear active hotkeys to prevent stale references to old segment objects
            self.active_hotkeys = {behavior: False for behavior in self.behavior_types}

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

        # Save updated segments (deep copy)
        self.videos[self.current_video_name][
            "segments"
        ] = self._deep_copy_segments(self.timeline.segments)

    # ------------------------------------------------------------------
    # Auto-labeling
    # ------------------------------------------------------------------

    def _resolve_qpos_for_video(self, video_name: str) -> Optional[str]:
        """Locate the qpos CSV for a video file by stem-matching."""
        try:
            from auto_labeler import resolve_qpos_path
        except ImportError:
            return None
        qpos_dir = getattr(self, "_qpos_dir", None)
        if not qpos_dir:
            return None
        return resolve_qpos_path(video_name, qpos_dir)

    def _resolve_qpos_pair_for_video(
        self, video_name: str
    ) -> Tuple[Optional[str], Optional[str]]:
        try:
            from auto_labeler import resolve_qpos_pair
        except ImportError:
            return None, None
        qpos_dir = getattr(self, "_qpos_dir", None)
        if not qpos_dir:
            return None, None
        return resolve_qpos_pair(video_name, qpos_dir)

    def _build_auto_segments(
        self, video_name: str
    ) -> Optional[List[BehaviorSegment]]:
        """Run the auto-labeler on a clip's qpos and return BehaviorSegment list.

        Returns None when qpos is not available for the clip.
        """
        from auto_labeler import auto_label_clip

        track_path, stac_path = self._resolve_qpos_pair_for_video(video_name)
        if not track_path:
            return None
        try:
            segs_raw = auto_label_clip(track_path, stac_path=stac_path)
        except Exception as e:
            QMessageBox.warning(
                self, "Auto-label error", f"Failed to auto-label {video_name}:\n{e}"
            )
            return None

        return [
            BehaviorSegment(
                name=s["name"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                start_frame=s["start_frame"],
                end_frame=s["end_frame"],
            )
            for s in segs_raw
        ]

    def auto_label_current(self) -> None:
        """Auto-label the current clip. Writes directly if no manual labels,
        else stores as auto_segments (overlay) and flags conflict."""
        if not self.current_video_name:
            QMessageBox.information(self, "No clip", "Select a clip first.")
            return

        self._push_undo()
        name = self.current_video_name

        self._ensure_video_metadata(name)

        auto_segs = self._build_auto_segments(name)
        if auto_segs is None:
            QMessageBox.warning(
                self,
                "No qpos",
                f"No track/stac qpos CSV found for {name}.",
            )
            return

        existing = self.videos[name].get("segments", [])
        if not existing:
            self.videos[name]["segments"] = auto_segs
            self.videos[name]["auto_segments"] = []
            self.videos[name]["has_conflict"] = False
            self.timeline.segments = self._deep_copy_segments(auto_segs)
            self.timeline.auto_segments = []
        else:
            self.videos[name]["auto_segments"] = auto_segs
            self.videos[name]["has_conflict"] = True
            self.timeline.auto_segments = self._deep_copy_segments(auto_segs)

        self._refresh_video_list_conflict_flags()
        self.timeline.update()

    def auto_label_all_unlabeled(self) -> None:
        """Run auto-labeler on every loaded clip that has no manual segments."""
        self._push_undo()
        count = 0
        for name in list(self.videos.keys()):
            if self.videos[name].get("segments"):
                continue
            self._ensure_video_metadata(name)
            auto_segs = self._build_auto_segments(name)
            if auto_segs is None:
                continue
            self.videos[name]["segments"] = auto_segs
            self.videos[name]["auto_segments"] = []
            self.videos[name]["has_conflict"] = False
            count += 1

        if self.current_video_name and self.current_video_name in self.videos:
            self.timeline.segments = self._deep_copy_segments(
                self.videos[self.current_video_name].get("segments", [])
            )
            self.timeline.auto_segments = self._deep_copy_segments(
                self.videos[self.current_video_name].get("auto_segments", [])
            )
            self.timeline.update()

        self._refresh_video_list_conflict_flags()
        QMessageBox.information(
            self,
            "Auto-label complete",
            f"Auto-labeled {count} unlabeled clips.",
        )

    def toggle_auto_overlay(self) -> None:
        self.timeline.show_auto_overlay = not self.timeline.show_auto_overlay
        self.timeline.update()

    # ------------------------------------------------------------------
    # Auto-directionality
    # ------------------------------------------------------------------

    def _build_auto_direction_segments(
        self, video_name: str
    ) -> Optional[List[BehaviorSegment]]:
        from auto_direction import auto_direction_clip

        track_path, stac_path = self._resolve_qpos_pair_for_video(video_name)
        if not track_path:
            return None
        # If Turn segments already exist on the behavior track, force the
        # direction inside each Turn to Left/Right (never Straight).
        turn_spans: List[Tuple[int, int]] = []
        for seg in self.videos.get(video_name, {}).get("segments", []) or []:
            if seg.name == "Turn" and seg.start_frame is not None and seg.end_frame is not None:
                turn_spans.append((int(seg.start_frame), int(seg.end_frame)))
        try:
            raw = auto_direction_clip(
                track_path,
                stac_path=stac_path,
                turn_frame_spans=turn_spans or None,
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Auto-directionality error", f"Failed on {video_name}:\n{e}"
            )
            return None
        return [
            BehaviorSegment(
                name=s["name"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                start_frame=s["start_frame"],
                end_frame=s["end_frame"],
            )
            for s in raw
        ]

    def auto_direction_current(self) -> None:
        """Run the auto-direction pipeline on the currently-selected clip."""
        if not self.current_video_name:
            QMessageBox.information(self, "No clip", "Select a clip first.")
            return

        name = self.current_video_name
        self._ensure_video_metadata(name)

        segs = self._build_auto_direction_segments(name)
        if segs is None:
            QMessageBox.warning(
                self,
                "No qpos",
                f"No track/stac qpos CSV found for {name}.",
            )
            return

        self._push_undo()
        self.videos[name]["direction_segments"] = segs
        self.timeline.direction_segments = self._deep_copy_segments(segs)
        self.timeline.update()

    def auto_direction_all(self) -> None:
        """Run auto-directionality on every loaded clip."""
        if not getattr(self, "_qpos_dir", None):
            return
        self._push_undo()
        count = 0
        for name in list(self.videos.keys()):
            self._ensure_video_metadata(name)
            segs = self._build_auto_direction_segments(name)
            if segs is None:
                continue
            self.videos[name]["direction_segments"] = segs
            count += 1
        if self.current_video_name and self.current_video_name in self.videos:
            self.timeline.direction_segments = self._deep_copy_segments(
                self.videos[self.current_video_name].get("direction_segments", [])
            )
            self.timeline.update()
        QMessageBox.information(
            self, "Auto-directionality complete", f"Processed {count} clips."
        )

    # ------------------------------------------------------------------
    # Conflict resolution via right-click context menu
    # ------------------------------------------------------------------

    def _on_timeline_context_menu(self, pos) -> None:
        """Context menu dispatch: direction strip vs behavior rows."""
        x, y = pos.x(), pos.y()

        if self.timeline.is_direction_strip_y(y):
            dir_seg = self.timeline.direction_segment_at(x)
            if dir_seg is None:
                return
            menu = QMenu(self)
            set_menu = menu.addMenu(f"Set direction ({dir_seg.name})")
            for label in ("Left", "Right", "Straight"):
                act = set_menu.addAction(label)
                act.triggered.connect(
                    lambda _=False, s=dir_seg, lbl=label: self._set_direction_label(s, lbl)
                )
            menu.exec_(self.timeline.mapToGlobal(pos))
            return

        seg, edge = self.timeline.get_segment_at_pos(x, y)
        auto_seg = self._auto_segment_at_pos(x, y)

        if seg is None and auto_seg is None:
            return

        menu = QMenu(self)

        if seg is not None:
            set_name = menu.addMenu(f"Change {seg.name!r} to …")
            for b in self.behavior_types:
                if b == seg.name:
                    continue
                act = set_name.addAction(b)
                act.triggered.connect(
                    lambda _=False, s=seg, new_name=b: self._rename_segment(s, new_name)
                )

            if auto_seg is not None:
                menu.addSeparator()
                replace = menu.addAction("Replace with Auto label")
                replace.triggered.connect(
                    lambda _=False, s=seg, a=auto_seg: self._replace_with_auto(s, a)
                )

            menu.addSeparator()
            delete_act = menu.addAction("Delete segment")
            delete_act.triggered.connect(self._delete_from_context_menu)

        if seg is None and auto_seg is not None:
            promote = menu.addAction("Promote Auto label to Manual")
            promote.triggered.connect(
                lambda _=False, a=auto_seg: self._promote_auto_segment(a)
            )

        menu.exec_(self.timeline.mapToGlobal(pos))

    def _rename_segment(self, seg: BehaviorSegment, new_name: str) -> None:
        self._push_undo()
        seg.name = new_name
        if new_name in BehaviorSegment._color_map:
            seg.color = BehaviorSegment._color_map[new_name]
        if self.current_video_name:
            self.videos[self.current_video_name]["segments"] = self._deep_copy_segments(
                self.timeline.segments
            )
        self.timeline.update()

    def _auto_segment_at_pos(self, x: int, y: int) -> Optional[BehaviorSegment]:
        """Find an auto segment whose overlay rectangle contains (x, y)."""
        if not self.timeline.show_auto_overlay or not self.timeline.auto_segments:
            return None
        w = self.timeline.width()
        overlay_h = max(8, int(self.timeline.row_height * 0.35))
        for seg in self.timeline.auto_segments:
            row_y = self.timeline.get_behavior_row(seg.name)
            x_start = (seg.start_time / self.timeline.duration) * w
            x_end = (
                (seg.end_time / self.timeline.duration) * w
                if seg.end_time is not None
                else x_start
            )
            y_top = row_y + self.timeline.row_height - overlay_h
            if y_top <= y <= row_y + self.timeline.row_height and x_start <= x <= x_end:
                return seg
        return None

    def _set_direction_label(self, seg: BehaviorSegment, label: str) -> None:
        """Change a direction-track segment's label (Left/Right/Straight)."""
        if label not in ("Left", "Right", "Straight"):
            return
        self._push_undo()
        seg.name = label
        if label in BehaviorSegment._color_map:
            seg.color = BehaviorSegment._color_map[label]
        if self.current_video_name:
            self.videos[self.current_video_name]["direction_segments"] = (
                self._deep_copy_segments(self.timeline.direction_segments)
            )
        self.timeline.update()

    def _delete_from_context_menu(self) -> None:
        if self.timeline.selected_segment is None:
            return
        self._push_undo()
        if self.timeline.delete_selected_segment() and self.current_video_name:
            self.videos[self.current_video_name]["segments"] = self._deep_copy_segments(
                self.timeline.segments
            )

    def _replace_with_auto(
        self, manual_seg: BehaviorSegment, auto_seg: BehaviorSegment
    ) -> None:
        """Swap a manual segment out for an auto segment of the same time range."""
        self._push_undo()
        if manual_seg in self.timeline.segments:
            self.timeline.segments.remove(manual_seg)
        self.timeline.segments.append(auto_seg.copy())
        if auto_seg in self.timeline.auto_segments:
            self.timeline.auto_segments.remove(auto_seg)
        if self.current_video_name:
            self.videos[self.current_video_name]["segments"] = self._deep_copy_segments(
                self.timeline.segments
            )
            self.videos[self.current_video_name]["auto_segments"] = self._deep_copy_segments(
                self.timeline.auto_segments
            )
            self.videos[self.current_video_name]["has_conflict"] = bool(
                self.timeline.auto_segments
            )
        self._refresh_video_list_conflict_flags()
        self.timeline.update()

    def _promote_auto_segment(self, auto_seg: BehaviorSegment) -> None:
        """Copy an auto segment into the manual timeline."""
        self._push_undo()
        self.timeline.segments.append(auto_seg.copy())
        if auto_seg in self.timeline.auto_segments:
            self.timeline.auto_segments.remove(auto_seg)
        if self.current_video_name:
            self.videos[self.current_video_name]["segments"] = self._deep_copy_segments(
                self.timeline.segments
            )
            self.videos[self.current_video_name]["auto_segments"] = self._deep_copy_segments(
                self.timeline.auto_segments
            )
            self.videos[self.current_video_name]["has_conflict"] = bool(
                self.timeline.auto_segments
            )
        self._refresh_video_list_conflict_flags()
        self.timeline.update()

    def _ensure_video_metadata(self, name: str) -> None:
        """Lazily populate fps/duration for a lazily-loaded video entry."""
        data = self.videos.get(name)
        if not data:
            return
        if data.get("fps") and data.get("duration"):
            return
        cap = cv2.VideoCapture(data["path"])
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        duration = total / fps if fps > 0 else 0.0
        data["fps"] = fps
        data["duration"] = duration
        data.setdefault("segments", [])
        data.setdefault("direction_segments", [])
        data.setdefault("auto_segments", [])
        data.setdefault("has_conflict", False)

    # ------------------------------------------------------------------
    # Startup auto-load
    # ------------------------------------------------------------------

    def _autoload_sample_dataset(self) -> None:
        """Load clips from sample/videos/ (lazy metadata).

        Per request, manual labels from the legacy CSV are NOT pre-populated.
        Every loaded clip gets auto-label + auto-directionality applied at
        startup by _deferred_autoassign.
        """
        script_dir = Path(__file__).resolve().parent
        videos_dir = script_dir / "sample" / "videos"
        csvs_dir = script_dir / "sample" / "csvs"

        if not videos_dir.is_dir():
            return

        self._qpos_dir = str(csvs_dir) if csvs_dir.is_dir() else None

        def clip_index(p: Path) -> int:
            stem = p.stem
            try:
                return int(stem.split("_")[-1])
            except ValueError:
                return -1

        LOAD_MAX = 841
        video_paths = sorted(
            (p for p in videos_dir.glob("clip_*.mp4") if 0 <= clip_index(p) <= LOAD_MAX),
            key=clip_index,
        )
        for vp in video_paths:
            name = vp.name
            if name in self.videos:
                continue
            self.videos[name] = {
                "path": str(vp),
                "segments": [],
                "direction_segments": [],
                "auto_segments": [],
                "has_conflict": False,
                "duration": 0.0,
                "fps": 0.0,
            }
            self.video_list.addItem(name)

        if self.video_list.count() > 0:
            self.video_list.setCurrentRow(0)

        QTimer.singleShot(300, self._deferred_autoassign)

    def _deferred_autoassign(self) -> None:
        """On startup: run auto-label AND auto-directionality on every clip.

        No manual labels are pre-loaded. The progress dialog covers both
        passes in a single loop per clip so we don't open the qpos CSV twice.
        """
        if not getattr(self, "_qpos_dir", None):
            return

        targets = list(self.videos.keys())
        if not targets:
            return

        progress = QProgressDialog(
            "Auto-assigning labels + direction…", "Cancel", 0, len(targets), self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        from auto_labeler import auto_label_clip, resolve_qpos_pair
        from auto_direction import auto_direction_clip

        labeled = 0
        for i, name in enumerate(targets):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            progress.setLabelText(f"Processing {name} ({i + 1}/{len(targets)})")
            QApplication.processEvents()

            track_path, stac_path = resolve_qpos_pair(name, self._qpos_dir)
            if not track_path:
                continue

            self._ensure_video_metadata(name)

            try:
                raw_beh = auto_label_clip(track_path, stac_path=stac_path)
                turn_spans = [
                    (int(s["start_frame"]), int(s["end_frame"]))
                    for s in raw_beh
                    if s["name"] == "Turn"
                ]
                raw_dir = auto_direction_clip(
                    track_path,
                    stac_path=stac_path,
                    turn_frame_spans=turn_spans or None,
                )
            except Exception:
                continue

            beh_segs = [
                BehaviorSegment(
                    name=s["name"],
                    start_time=s["start_time"],
                    end_time=s["end_time"],
                    start_frame=s["start_frame"],
                    end_frame=s["end_frame"],
                )
                for s in raw_beh
            ]
            dir_segs = [
                BehaviorSegment(
                    name=s["name"],
                    start_time=s["start_time"],
                    end_time=s["end_time"],
                    start_frame=s["start_frame"],
                    end_frame=s["end_frame"],
                )
                for s in raw_dir
            ]
            self.videos[name]["segments"] = beh_segs
            self.videos[name]["direction_segments"] = dir_segs
            labeled += 1

        progress.setValue(len(targets))

        if self.current_video_name and self.current_video_name in self.videos:
            self.timeline.segments = self._deep_copy_segments(
                self.videos[self.current_video_name].get("segments", [])
            )
            self.timeline.direction_segments = self._deep_copy_segments(
                self.videos[self.current_video_name].get("direction_segments", [])
            )
            self.timeline.update()

    def _autoload_labels(self, converted_csv: Path) -> None:
        """Silently import labels from the new two-track CSV into loaded videos."""
        try:
            with open(converted_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = set(reader.fieldnames or [])
                rows = list(reader)
        except Exception:
            return

        normalized = self._normalize_import_rows(rows, fieldnames)

        by_video: Dict[str, List[Dict[str, str]]] = {}
        for r in normalized:
            by_video.setdefault(r["Video"], []).append(r)

        behaviors_seen: set = set()
        for video_name, anns in by_video.items():
            if video_name not in self.videos:
                continue
            self._ensure_video_metadata(video_name)
            fps = self.videos[video_name]["fps"] or 30.0
            behavior_segs: List[BehaviorSegment] = []
            direction_segs: List[BehaviorSegment] = []
            for ann in anns:
                try:
                    ts = float(ann["Start_Time"])
                    te_str = ann.get("End_Time", "").strip()
                    te = float(te_str) if te_str else None
                    fs_str = ann.get("Start_Frame", "").strip()
                    fe_str = ann.get("End_Frame", "").strip()
                    fs = int(fs_str) if fs_str else int(ts * fps)
                    fe = (
                        int(fe_str)
                        if fe_str
                        else (int(te * fps) if te is not None else None)
                    )
                    label = ann["Label"]
                    seg = BehaviorSegment(
                        name=label,
                        start_time=ts,
                        end_time=te,
                        start_frame=fs,
                        end_frame=fe,
                    )
                    if ann.get("Track", "behavior") == "direction":
                        direction_segs.append(seg)
                    else:
                        behavior_segs.append(seg)
                        behaviors_seen.add(label)
                except (ValueError, KeyError):
                    continue
            self.videos[video_name]["segments"] = behavior_segs
            self.videos[video_name]["direction_segments"] = direction_segs

        for b in behaviors_seen:
            if b not in self.behavior_types:
                self.behavior_types.append(b)
                for char in b:
                    if char.isalpha():
                        key_code = getattr(Qt, f"Key_{char.upper()}", None)
                        if key_code and key_code not in self.behavior_hotkeys.values():
                            self.behavior_hotkeys[b] = key_code
                            break

        self.timeline.update_behavior_types(self.behavior_types)
        self.update_behavior_table()
        self.update_behavior_list()


def _build_app_icon() -> QIcon:
    """Procedurally render a multi-size app icon so macOS doesn't show the
    generic document icon. Style mirrors the timeline: a thin direction
    strip over stacked behavior rows on a rounded card.
    """
    icon = QIcon()
    for size in (32, 64, 128, 256, 512):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Rounded card background (black)
        card = QColor("#0b0d12")
        p.setBrush(QBrush(card))
        p.setPen(Qt.NoPen)
        pad = size // 10
        r = size - 2 * pad
        p.drawRoundedRect(pad, pad, r, r, r // 5, r // 5)

        # Direction strip (top)
        strip_h = max(3, r // 10)
        strip_y = pad + r // 6
        inner_pad = r // 8
        bar_w = r - 2 * inner_pad
        third = bar_w // 3
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawRect(pad + inner_pad, strip_y, third, strip_h)
        p.setBrush(QBrush(QColor("#f97316")))
        p.drawRect(pad + inner_pad + third, strip_y, third, strip_h)
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawRect(pad + inner_pad + 2 * third, strip_y, bar_w - 2 * third, strip_h)

        # Three behavior rows
        row_h = max(3, r // 10)
        gap = max(1, r // 40)
        y = strip_y + strip_h + row_h
        bars = [
            (QColor("#f59e0b"), 0.10, 0.55),
            (QColor("#ef4444"), 0.35, 0.90),
            (QColor("#22c55e"), 0.05, 0.45),
        ]
        for color, start, end in bars:
            x0 = pad + inner_pad + int(start * bar_w)
            x1 = pad + inner_pad + int(end * bar_w)
            p.setBrush(QBrush(color))
            p.drawRect(x0, y, max(2, x1 - x0), row_h)
            y += row_h + gap

        # Playhead line
        p.setPen(QPen(QColor("#ffffff"), max(1, size // 96)))
        ph_x = pad + inner_pad + int(0.62 * bar_w)
        p.drawLine(ph_x, strip_y, ph_x, y - gap)

        p.end()
        icon.addPixmap(pm)
    return icon


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app)
    app.setApplicationName("TopoMimic Annotation")
    icon = _build_app_icon()
    app.setWindowIcon(icon)
    window = AnnotatorGUI()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec_())
