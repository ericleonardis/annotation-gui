import sys
import cv2
import csv
import os
import random
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
    QAction,
    QMessageBox,
    QInputDialog,
    QSplitter,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QKeySequence


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
    # Class variable to store color mapping
    _color_map = {
        "Immobility": QColor(255, 100, 100, 150),
        "Rear": QColor(100, 255, 100, 150),
        "Groom": QColor(100, 150, 255, 150),
    }
    _used_colors = set([(255, 100, 100), (100, 255, 100), (100, 150, 255)])

    def __init__(
        self, name, start_time, end_time=None, start_frame=None, end_frame=None
    ):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.start_frame = start_frame
        self.end_frame = end_frame

        # Get or assign color for this behavior
        if name not in BehaviorSegment._color_map:
            BehaviorSegment._color_map[name] = BehaviorSegment._get_new_color()

        self.color = BehaviorSegment._color_map[name]

    @classmethod
    def _get_new_color(cls):
        """Get a new distinct color from the palette."""
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
    def remove_behavior_color(cls, behavior_name):
        """Remove a behavior's color mapping."""
        if behavior_name in cls._color_map:
            color = cls._color_map[behavior_name]
            color_tuple = (color.red(), color.green(), color.blue())
            if color_tuple in cls._used_colors:
                cls._used_colors.discard(color_tuple)
            del cls._color_map[behavior_name]


class TimelineWidget(QWidget):
    clicked_pos = pyqtSignal(float)
    dragging = pyqtSignal(float)
    segment_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 1.0
        self.current_time = 0.0
        self.segments = []
        self.setMinimumHeight(150)
        self.active_behavior = None

        # Drag state
        self.is_dragging = False
        self.drag_segment = None
        self.drag_edge = None
        self.EDGE_THRESHOLD = 10

        # Scrubbing state
        self.is_scrubbing = False

        # Selection state
        self.selected_segment = None

        # Behavior rows
        self.behavior_types = ["Immobility", "Rear", "Groom"]
        self.row_height = 40

    def update_behavior_types(self, behaviors):
        """Update the list of behavior types."""
        self.behavior_types = behaviors
        self.update()

    def get_behavior_row(self, behavior_name):
        """Get the y position for a behavior type."""
        if behavior_name in self.behavior_types:
            idx = self.behavior_types.index(behavior_name)
            return 10 + idx * (self.row_height + 5)
        return 10

    def get_segment_at_pos(self, x, y):
        """Find segment and edge at given position."""
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

    def paintEvent(self, event):
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

    def mousePressEvent(self, event):
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

    def mouseMoveEvent(self, event):
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

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.is_scrubbing = False
        self.drag_segment = None
        self.drag_edge = None
        self.setCursor(Qt.ArrowCursor)

    def delete_selected_segment(self):
        """Delete the currently selected segment."""
        if self.selected_segment and self.selected_segment in self.segments:
            self.segments.remove(self.selected_segment)
            self.selected_segment = None
            self.segment_selected.emit(None)
            self.update()
            return True
        return False


class AnnotatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Behavior Annotator")
        self.setGeometry(100, 100, 1200, 700)

        # Video management
        self.videos = {}
        self.current_video_name = None

        # State
        self.cap = None
        self.is_playing = False
        self.current_seg = None

        # Hotkey tracking
        self.active_hotkeys = {}

        # Behavior hotkey mapping
        self.behavior_hotkeys = {
            "Immobility": Qt.Key_I,
            "Rear": Qt.Key_R,
            "Groom": Qt.Key_G,
        }

        # Global behavior types
        self.behavior_types = ["Immobility", "Rear", "Groom"]

        # UI Setup
        self.init_ui()

        # Timer for video playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

    def init_ui(self):
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
        self.timeline.behavior_types = self.behavior_types
        self.timeline.installEventFilter(self)
        right_layout.addWidget(self.timeline, 1)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_play = QPushButton("Play/Pause (Space)")
        self.btn_play.clicked.connect(self.toggle_play)

        self.behavior_list = QListWidget()
        self.update_behavior_list()
        self.behavior_list.setFixedHeight(100)
        self.behavior_list.installEventFilter(self)

        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.behavior_list)
        right_layout.addLayout(ctrl_layout)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        layout.addWidget(splitter)

    def switch_video(self, current, previous):
        """Switch to a different video."""
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

    def remove_video(self):
        """Remove the currently selected video."""
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

    def on_segment_selected(self, segment):
        """Handle segment selection."""
        pass

    def update_behavior_list(self):
        """Update the behavior list with hotkey labels."""
        self.behavior_list.clear()
        for behavior in self.behavior_types:
            if behavior in self.behavior_hotkeys:
                key = self.behavior_hotkeys[behavior]
                key_name = QKeySequence(key).toString()
                self.behavior_list.addItem(f"{behavior} ({key_name})")
            else:
                self.behavior_list.addItem(behavior)

    def add_new_behavior(self):
        """Add a new behavior type."""
        text, ok = QInputDialog.getText(
            self, "Add New Behavior", "Enter behavior name:"
        )
        if ok and text:
            if text not in self.behavior_types:
                self.behavior_types.append(text)

                # Assign a hotkey
                if text:
                    key_name = text[0].upper()
                    key_code = getattr(Qt, f"Key_{key_name}", None)
                    if key_code and key_code not in self.behavior_hotkeys.values():
                        self.behavior_hotkeys[text] = key_code

                self.timeline.update_behavior_types(self.behavior_types)
                self.update_behavior_list()

                min_height = 20 + len(self.behavior_types) * 45
                self.timeline.setMinimumHeight(min_height)

    def delete_behavior(self):
        """Delete a behavior type from all videos."""
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
                self.update_behavior_list()
                self.timeline.update()

                min_height = 20 + len(self.behavior_types) * 45
                self.timeline.setMinimumHeight(max(150, min_height))

    def eventFilter(self, obj, event):
        # Handle keyboard events for all child widgets
        if event.type() == event.KeyPress:
            if event.key() == Qt.Key_Space:
                self.toggle_play()
                return True
            elif event.key() in (Qt.Key_Enter, Qt.Key_Return):
                if obj == self.behavior_list:
                    self.handle_annotation()
                    return True
            elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                if self.timeline.delete_selected_segment():
                    if self.current_video_name:
                        self.videos[self.current_video_name][
                            "segments"
                        ] = self.timeline.segments.copy()
                return True
            else:
                # Check for behavior hotkeys
                for behavior, key in self.behavior_hotkeys.items():
                    if event.key() == key and not event.isAutoRepeat():
                        self.start_behavior_annotation(behavior)
                        return True
        elif event.type() == event.KeyRelease:
            # Handle hotkey release
            for behavior, key in self.behavior_hotkeys.items():
                if event.key() == key and not event.isAutoRepeat():
                    if self.active_hotkeys.get(behavior, False):
                        self.stop_behavior_annotation(behavior)
                    return True

        return super().eventFilter(obj, event)

    def load_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Video")
        if path:
            video_name = os.path.basename(path)

            # Check if already loaded
            if video_name in self.videos:
                QMessageBox.warning(self, "Duplicate", "This video is already loaded.")
                return

            # Get video properties
            cap = cv2.VideoCapture(path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
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
            self.video_list.setCurrentRow(self.video_list.count() - 1)

    def keyPressEvent(self, event):
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

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return

        # Check if a behavior hotkey was released
        for behavior, key in self.behavior_hotkeys.items():
            if event.key() == key and self.active_hotkeys.get(behavior, False):
                self.stop_behavior_annotation(behavior)
                break

    def start_behavior_annotation(self, behavior_name):
        """Start annotation for a specific behavior."""
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

    def stop_behavior_annotation(self, behavior_name):
        """Stop annotation for a specific behavior."""
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

    def handle_annotation(self):
        """Handle Enter key annotation (legacy method)."""
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

    def toggle_play(self):
        if not self.cap:
            return

        if self.is_playing:
            self.timer.stop()
        else:
            fps = self.videos[self.current_video_name]["fps"]
            self.timer.start(int(1000 / fps))
        self.is_playing = not self.is_playing

    def update_frame(self):
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

    def seek_video(self, time_sec):
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000.0)
            self.update_frame()

    def export_csv(self):
        """Export all videos and annotations to CSV."""
        # Save current video segments
        if self.current_video_name and self.current_video_name in self.videos:
            self.videos[self.current_video_name][
                "segments"
            ] = self.timeline.segments.copy()

        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if path:
            with open(path, "w", newline="") as f:
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnnotatorGUI()
    window.show()
    sys.exit(app.exec_())
