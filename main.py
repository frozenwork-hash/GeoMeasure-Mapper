import sys
import math
import os
import fitz  # PyMuPDF for working with PDFs
from PyQt6.QtWidgets import (
    QCheckBox,
    QSpinBox,
    QDialogButtonBox,
    QApplication,
    QMainWindow,
    QColorDialog,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsTextItem,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QTextEdit,
    QLabel,
    QDialog,
    QFormLayout,
    QDoubleSpinBox,
    QComboBox,
    QMessageBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QInputDialog,
    QMenu,
)
from PyQt6.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt6.QtGui import QImageReader, QPixmap, QMouseEvent, QPen, QBrush, QColor, QPainter, QImage, QCursor, QFont, QPainterPath

from exporter import (
    CSVExporter,
    ExportError,
    ExportManager,
    JSONExporter,
    PDFExporter,
    PNGExporter,
)

UNIT_TO_METERS = {
    "m": 1.0,
    "km": 1000.0,
    "miles (mi)": 1609.344,
    "nautical miles (nmi)": 1852.0,
    "feet (ft)": 0.3048,
    "cm": 0.01,
    "mm": 0.001,
}

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".pdf"}
IMAGE_FILE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff, *.pdf);;PDF Documents (*.pdf)"



def is_image_file(file_path: str) -> bool:
    return os.path.splitext(file_path)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


class CalibrationDialog(QDialog):
    def __init__(self, dist_px, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map Scale Calibration")
        self.setFixedWidth(320)

        layout = QFormLayout(self)
        self.lbl_px = QLabel(f"<b>{dist_px:.2f} px</b>")
        layout.addRow("Segment length on the map:", self.lbl_px)

        self.spin_val = QDoubleSpinBox()
        self.spin_val.setRange(0.00001, 1000000.0)
        self.spin_val.setValue(1.0)
        self.spin_val.setDecimals(4)
        layout.addRow("Real-world length:", self.spin_val)

        self.combo_unit = QComboBox()
        self.combo_unit.addItems(list(UNIT_TO_METERS.keys()))
        self.combo_unit.setCurrentText("km")
        layout.addRow("Unit:", self.combo_unit)

        btn_apply = QPushButton("Apply Scale")
        btn_apply.clicked.connect(self.accept)
        layout.addRow(btn_apply)

    def get_values(self):
        return self.spin_val.value(), self.combo_unit.currentText()


class CompassItem(QGraphicsItem):
    """Custom compass item with an 8-point star, letters, and directional rays."""

    def __init__(self, x=0, y=0, radius=40, ray_length=2000, parent=None):
        super().__init__(parent)
        self.setPos(x, y)
        self.radius = radius            # Radius of the star itself
        self.ray_length = ray_length    # Length of the directional rays

        # Interaction settings
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(5)  # Draw above the map, but below the measurement points

        self._is_rotating = False
        self._last_mouse_angle = 0.0

    def shape(self) -> QPainterPath:
        """Restricts the clickable area to the central part of the star,
        so the long rays don't block interaction with the map."""
        path = QPainterPath()
        # Make only the star itself (a circle of radius self.radius) clickable
        path.addEllipse(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        return path

    def boundingRect(self) -> QRectF:
        # The item's bounds account for the length of the directional rays
        total_size = self.radius + self.ray_length
        return QRectF(-total_size, -total_size, total_size * 2, total_size * 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw the directional rays from the 8 tips of the star
        pen_rays = QPen(QColor(217, 4, 41, 140), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen_rays)

        # 8 rays every 45 degrees (0 = North / Up)
        for i in range(8):
            angle_rad = math.radians(i * 45 - 90)
            dx = math.cos(angle_rad) * self.ray_length
            dy = math.sin(angle_rad) * self.ray_length
            start_x = math.cos(angle_rad) * self.radius
            start_y = math.sin(angle_rad) * self.radius
            painter.drawLine(QLineF(start_x, start_y, dx, dy))

        # 2. Draw the 8-point star
        r_outer = self.radius
        r_inner = self.radius * 0.38

        # Draw the 8 main star points (alternating dark and light facets)
        for i in range(8):
            angle_curr = math.radians(i * 45 - 90)
            angle_next = math.radians((i + 1) * 45 - 90)
            angle_mid = math.radians(i * 45 + 22.5 - 90)

            # Left half of the point (dark)
            p1 = QPointF(0, 0)
            p2 = QPointF(r_outer * math.cos(angle_curr), r_outer * math.sin(angle_curr))
            p3 = QPointF(r_inner * math.cos(angle_mid), r_inner * math.sin(angle_mid))

            path_dark = QPainterPath()
            path_dark.moveTo(p1)
            path_dark.lineTo(p2)
            path_dark.lineTo(p3)
            path_dark.closeSubpath()

            painter.setPen(QPen(QColor(30, 41, 59), 1))
            # Highlight the North ray in red
            if i == 0:
                painter.setBrush(QBrush(QColor(217, 4, 41)))
            else:
                painter.setBrush(QBrush(QColor(30, 41, 59)))
            painter.drawPath(path_dark)

            # Right half of the point (light)
            p4 = QPointF(r_outer * math.cos(angle_next), r_outer * math.sin(angle_next))

            path_light = QPainterPath()
            path_light.moveTo(p1)
            path_light.lineTo(p3)
            path_light.lineTo(p4)
            path_light.closeSubpath()

            if i == 0:
                painter.setBrush(QBrush(QColor(239, 68, 68)))
            else:
                painter.setBrush(QBrush(QColor(100, 116, 139)))
            painter.drawPath(path_light)

        # 3. Draw the N, S, E, W letters
        painter.setPen(QPen(QColor(15, 23, 42)))
        font = QFont("sans-serif", 10, QFont.Weight.Bold)
        painter.setFont(font)

        labels = [
            ("N", 0, -self.radius - 14),
            ("E", self.radius + 14, 0),
            ("S", 0, self.radius + 14),
            ("W", -self.radius - 14, 0)
        ]

        for text, lx, ly in labels:
            rect = QRectF(lx - 12, ly - 12, 24, 24)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    # --- ROTATION AND DELETION LOGIC ---

    def mousePressEvent(self, event):
        # Right click — delete the compass
        if event.button() == Qt.MouseButton.RightButton:
            menu = QMenu()
            action_delete = menu.addAction("Delete Compass")
            if menu.exec(event.screenPos()) == action_delete:
                if self.scene():
                    self.scene().removeItem(self)
            return

        # Alt + Left click — enable rotation mode
        if event.button() == Qt.MouseButton.LeftButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self._is_rotating = True
            pos = event.pos()
            self._last_mouse_angle = math.degrees(math.atan2(pos.y(), pos.x()))
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_rotating:
            pos = event.pos()
            current_angle = math.degrees(math.atan2(pos.y(), pos.x()))
            delta_angle = current_angle - self._last_mouse_angle
            self.setRotation(self.rotation() + delta_angle)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_rotating = False
        super().mouseReleaseEvent(event)


class SettingsDialog(QDialog):
    def __init__(self, auto_break: bool, pdf_res: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setFixedWidth(380)

        layout = QFormLayout(self)

        # 1. Auto-break toggle
        self.chk_auto_break = QCheckBox()
        self.chk_auto_break.setChecked(auto_break)
        layout.addRow("Break the line when the color changes:", self.chk_auto_break)

        # 2. PDF render quality (max_side_target)
        self.spin_pdf_res = QSpinBox()
        self.spin_pdf_res.setRange(1024, 16384)
        self.spin_pdf_res.setSingleStep(1024)
        self.spin_pdf_res.setValue(pdf_res)
        layout.addRow("Max. PDF render resolution (px):", self.spin_pdf_res)

        # 3. Physical window resolution
        self.combo_screen_res = QComboBox()
        self.combo_screen_res.addItems([
            "Don't change",
            "1280x720",
            "1600x900",
            "1920x1080",
            "2560x1440"
        ])
        layout.addRow("Application window resolution:", self.combo_screen_res)

        # OK/Cancel buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def get_values(self):
        return (
            self.chk_auto_break.isChecked(),
            self.spin_pdf_res.value(),
            self.combo_screen_res.currentText()
        )

class PointItem(QGraphicsEllipseItem):
    """A draggable point with a sequence number inside it"""

    def __init__(self, x, y, index, radius=9, view=None):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.index = index
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(230, 30, 30)))
        self.setPen(QPen(Qt.GlobalColor.white, 2))
        self.setZValue(10)

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.view = view

    def paint(self, painter, option, widget=None):
        # 1. First draw the point itself (the circle)
        super().paint(painter, option, widget)

        # 2. Set up the font and color for the text
        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)

        # 3. Draw the number centered within the item's bounds (boundingRect)
        painter.drawText(
            self.boundingRect(),
            Qt.AlignmentFlag.AlignCenter,
            str(self.index)
        )

    def mousePressEvent(self, event):
        # Right click on a point — delete context menu
        if event.button() == Qt.MouseButton.RightButton:
            menu = QMenu()
            action_delete = menu.addAction("Delete Point")
            if menu.exec(event.screenPos()) == action_delete:
                if self.view:
                    self.view.delete_point(self)
            event.accept()
            return

        # If the point-merge mode is active, intercept the left click
        if event.button() == Qt.MouseButton.LeftButton and self.view and self.view.mode == "MERGE":
            self.view.handle_merge_click(self)
            event.accept()
            return

        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.view:
                self.view.on_point_moved()
        return super().itemChange(change, value)


class InteractiveView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = GridScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.points = []
        self.lines = []
        self.meters_per_pixel = None
        self.mode = "IDLE"
        self._break_line = False

        self.current_line_color = QColor(0, 191, 255)

        self.calib_start = None
        self.calib_marker = None
        self.main_window = parent

        # Navigation settings (zoom and panning)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)


    def delete_point(self, point_item):
        """Deletes a point, removes the lines connected to it, and recalculates indices."""
        # Find and remove all lines connected to this point
        lines_to_remove = []
        for line_data in self.lines:
            if line_data["p1"] == point_item or line_data["p2"] == point_item:
                lines_to_remove.append(line_data)

        for ld in lines_to_remove:
            if ld["item"].scene():
                self.scene.removeItem(ld["item"])
            self.lines.remove(ld)

        # Remove the point itself from the scene and the list
        if point_item.scene():
            self.scene.removeItem(point_item)
        if point_item in self.points:
            self.points.remove(point_item)

        # Recalculate the sequence numbers (indices) of the remaining points
        for idx, pt in enumerate(self.points):
            pt.index = idx + 1
            pt.update()

        # Update the geometry of the remaining lines (in case of shifts)
        self.on_point_moved()
        if self.main_window:
            self.main_window.update_calculations()
            self.main_window.set_status("Point deleted, lines broken, indices updated.")

    def handle_merge_click(self, point_item):
        """Handles point selection for the merge tool."""
        if not hasattr(self, "_merge_source") or self._merge_source is None:
            self._merge_source = point_item
            if self.main_window:
                self.main_window.set_status(f"Point #{point_item.index} selected for merging. Click the second point.")
        else:
            source = self._merge_source
            target = point_item
            self.merge_points(source, target)

            if source == target:
                if self.main_window:
                    self.main_window.set_status("Cannot merge a point with itself. Choose another one.")
                return

            self.merge_points(source, target)

    def merge_points(self, source, target):
        """Connects two existing points with a line (merges them) without deleting either."""
        if source == target:
            if self.main_window:
                self.main_window.set_status("Cannot connect a point to itself. Choose another one.")
            return

        # Check whether a line already exists between these points
        for ld in self.lines:
            if (ld["p1"] == source and ld["p2"] == target) or (ld["p1"] == target and ld["p2"] == source):
                if self.main_window:
                    self.main_window.set_status("A line already connects these points!")
                self.reset_merge_state()
                return

        p1 = source.scenePos()
        p2 = target.scenePos()

        # Create a new segment between the points using the current line color
        line_item = self.scene.addLine(
            p1.x(), p1.y(),
            p2.x(), p2.y(),
            QPen(self.current_line_color, 3),
        )
        line_item.setZValue(1)

        # Add it to the list of lines
        self.lines.append({
            "item": line_item,
            "p1": source,
            "p2": target
        })

        self.reset_merge_state()
        self.on_point_moved()

        if self.main_window:
            self.main_window.update_calculations()
            self.main_window.set_status(f"Points #{source.index} and #{target.index} successfully connected by a line!")

    def reset_merge_state(self):
        """Resets the state of the merge tool."""
        self._merge_source = None
        self.mode = "IDLE"
        if self.main_window and hasattr(self.main_window, "btn_merge_points"):
            self.main_window.btn_merge_points.setChecked(False)
            self.main_window.btn_merge_points.setStyleSheet("")


    def start_new_line(self):
        """Sets the flag to start a new line on the next click."""
        if self.points:
            self._break_line = True
            if self.main_window:
                self.main_window.set_status("New line mode: click to start a separate route.")

    def wheelEvent(self, event):
        """Zoom the map with the mouse wheel"""
        zoom_factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(zoom_factor, zoom_factor)
        else:
            self.scale(1 / zoom_factor, 1 / zoom_factor)

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())

        # 1. If left click on a point — always drag it
        if event.button() == Qt.MouseButton.LeftButton and isinstance(item, PointItem):
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            super().mousePressEvent(event)
            return

        # 2. Handle a left click on empty space
        if event.button() == Qt.MouseButton.LeftButton:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            scene_pos = self.mapToScene(event.position().toPoint())

            if self.mode == "CALIBRATE":
                self.handle_calibration_click(scene_pos)
            elif self.mode == "POINTS":
                self.add_measurement_point(scene_pos)
            else:
                # In "IDLE" mode, clicking on empty space does nothing (or acts as canvas dragging)
                super().mousePressEvent(event)
            return

        # 3. Holding the RIGHT or MIDDLE mouse button — pan the map
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            dummy_event = QMouseEvent(
                event.type(),
                event.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                event.modifiers(),
            )
            super().mousePressEvent(dummy_event)
            return

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            dummy_event = QMouseEvent(
                event.type(),
                event.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                event.modifiers(),
            )
            super().mouseReleaseEvent(dummy_event)
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            return

        super().mouseReleaseEvent(event)

    def handle_calibration_click(self, pos: QPointF):
        if self.calib_start is None:
            self.calib_start = pos
            r = 5
            self.calib_marker = self.scene.addEllipse(
                pos.x() - r,
                pos.y() - r,
                r * 2,
                r * 2,
                QPen(QColor(255, 140, 0)),
                QBrush(QColor(255, 140, 0)),
            )
            if self.main_window:
                self.main_window.set_status(
                    "Calibration: click the second point of the reference segment."
                )
        else:
            calib_end = pos
            dist_px = math.hypot(
                calib_end.x() - self.calib_start.x(),
                calib_end.y() - self.calib_start.y(),
            )

            if dist_px < 2.0:
                QMessageBox.warning(self, "Error", "The points are too close together!")
                self.reset_calibration_state()
                return

            calib_line = self.scene.addLine(
                self.calib_start.x(),
                self.calib_start.y(),
                calib_end.x(),
                calib_end.y(),
                QPen(QColor(255, 140, 0), 2, Qt.PenStyle.DashLine),
            )

            dlg = CalibrationDialog(dist_px, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                real_val, unit_name = dlg.get_values()
                meters_val = real_val * UNIT_TO_METERS[unit_name]
                self.meters_per_pixel = meters_val / dist_px
                QMessageBox.information(
                    self,
                    "Scale Set",
                    f"Calibration complete!\n1 px = {self.meters_per_pixel:.5f} m",
                )

            if calib_line and calib_line.scene():
                self.scene.removeItem(calib_line)

            self.reset_calibration_state()
            if self.main_window:
                self.main_window.update_calculations()

    def reset_calibration_state(self):
        """Safely resets the calibration state"""
        if self.calib_marker and self.calib_marker.scene():
            self.scene.removeItem(self.calib_marker)
        self.calib_start = None
        self.calib_marker = None
        self._merge_source = None
        self.mode = "IDLE"  # Return to idle mode
        if self.main_window:
            self.main_window.set_status("Mode: View. Press 'Place Points' to take measurements.")


    def add_measurement_point(self, pos: QPointF):
        # Compute the sequence number for the new point
        point_index = len(self.points) + 1

        pt_item = PointItem(pos.x(), pos.y(), index=point_index, radius=9, view=self)
        self.scene.addItem(pt_item)

        # Draw a line only if there are previous points AND the line wasn't broken
        if self.points and not getattr(self, '_break_line', False):
            prev_pt = self.points[-1]
            p1 = prev_pt.scenePos()
            p2 = pt_item.scenePos()

            line_item = self.scene.addLine(
                p1.x(),
                p1.y(),
                p2.x(),
                p2.y(),
                QPen(self.current_line_color, 3),
            )
            line_item.setZValue(1)

            self.lines.append({
                "item": line_item,
                "p1": prev_pt,
                "p2": pt_item
            })

        self.points.append(pt_item)
        self._break_line = False

        if self.main_window:
            self.main_window.update_calculations()

    def on_point_moved(self):
        # IMPORTANT: the loop now iterates over dicts (line_data), not just lines
        for line_data in self.lines:
            p1 = line_data["p1"].scenePos()
            p2 = line_data["p2"].scenePos()
            line_data["item"].setLine(p1.x(), p1.y(), p2.x(), p2.y())

        if self.main_window:
            self.main_window.update_calculations()


class GridScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_grid = False
        self.grid_step_px = 100.0
        self.grid_value = 100.0
        self.grid_unit = "px (pixels)"

    def drawForeground(self, painter, rect):
        """Draws the grid, rigidly locked to the scene coordinates."""
        super().drawForeground(painter, rect)

        if self.show_grid and self.grid_step_px > 5:
            painter.setPen(QPen(QColor(0, 0, 0, 60), 1, Qt.PenStyle.DashLine))

            # Rigidly lock the grid coordinates to the scene's absolute coordinates (modulo)
            # This completely eliminates jitter when the camera moves.
            left = int(rect.left()) - (int(rect.left()) % int(self.grid_step_px))
            top = int(rect.top()) - (int(rect.top()) % int(self.grid_step_px))

            lines = []

            x = left
            while x < rect.right():
                lines.append(QLineF(x, rect.top(), x, rect.bottom()))
                x += self.grid_step_px

            y = top
            while y < rect.bottom():
                lines.append(QLineF(rect.left(), y, rect.right(), y))
                y += self.grid_step_px

            painter.drawLines(lines)

class GridDialog(QDialog):
    def __init__(self, current_val, current_unit, is_calibrated, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Grid Settings")
        self.setFixedWidth(350)
        layout = QFormLayout(self)

        self.chk_enable = QCheckBox("Show grid on canvas")
        self.chk_enable.setChecked(True)
        layout.addRow(self.chk_enable)

        self.spin_val = QDoubleSpinBox()
        self.spin_val.setRange(0.01, 100000.0)
        self.spin_val.setValue(current_val if current_val else 100.0)
        self.spin_val.setDecimals(2)
        layout.addRow("Cell size:", self.spin_val)

        self.combo_unit = QComboBox()
        self.combo_unit.addItems(["px (pixels)", "cm (on screen)"])
        # Only add real-world units if calibration has been done
        if is_calibrated:
            self.combo_unit.addItems(list(UNIT_TO_METERS.keys()))

        # Set the current value
        if current_unit:
            self.combo_unit.setCurrentText(current_unit)

        layout.addRow("Unit:", self.combo_unit)

        # --- RESET BUTTON ADDED ---
        self.btn_reset = QPushButton("Reset Grid")
        self.btn_reset.clicked.connect(self.reset_settings)
        layout.addRow("", self.btn_reset) # Leave the first argument empty so the button neatly sits in the right column

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def reset_settings(self):
        """Resets the form values to their defaults."""
        self.chk_enable.setChecked(False) # Uncheck the display option
        self.spin_val.setValue(100.0)     # Restore the default size
        self.combo_unit.setCurrentText("px (pixels)") # Restore the base unit

    def get_values(self):
        return self.chk_enable.isChecked(), self.spin_val.value(), self.combo_unit.currentText()

class MainWindow(QMainWindow):

    def set_info_text_color(self, hex_color: str):
        """Sets the report text color and updates the interface."""
        self.text_color_hex = hex_color
        # Apply the color to the widget
        self.info_text.setStyleSheet(
            f"background-color: #a8dadc; border: 1px solid #ced4da; color: {self.text_color_hex};"
        )
        self.update_calculations()

    def choose_text_color(self):
        """Opens the PyQt6 palette for interactively choosing a color."""
        color = QColorDialog.getColor(
            QColor(self.text_color_hex), self, "Choose the report text color"
        )
        if color.isValid():
            self.set_info_text_color(color.name())

    def __init__(self):
        super().__init__()
        self.text_color_hex = "#1d3557"
        self.setWindowTitle("Geo-Measure (Modular Export)")
        self.resize(1200, 850)

        self.auto_break_on_color_change = True  # Break flag
        self.pdf_max_resolution = 4096          # Base resolution for PDF

        self.export_manager = ExportManager()
        self.export_manager.register(PNGExporter())
        self.export_manager.register(PDFExporter())
        self.export_manager.register(CSVExporter())
        self.export_manager.register(JSONExporter())

        main_widget = QWidget()
        layout = QHBoxLayout(main_widget)

        self.view = InteractiveView(self)
        layout.addWidget(self.view, stretch=3)

        right_panel = QWidget()
        right_panel.setFixedWidth(280)
        panel_layout = QVBoxLayout(right_panel)

        self.btn_load = QPushButton("Load Map")
        self.btn_load.clicked.connect(self.load_image)
        self.btn_load.setMinimumHeight(40)
        panel_layout.addWidget(self.btn_load)

        self.btn_calibrate = QPushButton("Set Scale")
        self.btn_calibrate.clicked.connect(self.start_calibration)
        panel_layout.addWidget(self.btn_calibrate)

        # Add the point-placement mode toggle button
        self.btn_toggle_points = QPushButton("Place Points")
        self.btn_toggle_points.setCheckable(True)  # Make it a toggle button (pressed/released)
        self.btn_toggle_points.clicked.connect(self.toggle_points_mode)
        panel_layout.addWidget(self.btn_toggle_points)

        self.btn_color = QPushButton("Choose Line Color")
        self.btn_color.clicked.connect(self.choose_line_color)
        panel_layout.addWidget(self.btn_color)

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(self.open_settings)
        panel_layout.addWidget(self.btn_settings)

        out_unit_widget = QWidget()
        out_unit_layout = QHBoxLayout(out_unit_widget)
        out_unit_layout.setContentsMargins(0, 0, 0, 0)
        out_unit_layout.addWidget(QLabel("Units:"))
        self.combo_output_unit = QComboBox()
        self.combo_output_unit.addItems(["px (pixels)"] + list(UNIT_TO_METERS.keys()))
        self.combo_output_unit.setCurrentText("km")
        self.combo_output_unit.currentTextChanged.connect(self.update_calculations)
        out_unit_layout.addWidget(self.combo_output_unit)
        panel_layout.addWidget(out_unit_widget)

        # --- NEW BUTTON ---
        self.btn_new_line = QPushButton("Start New Line")
        self.btn_new_line.clicked.connect(self.view.start_new_line)
        panel_layout.addWidget(self.btn_new_line)
        # --------------------

        # Point-merge mode button
        self.btn_merge_points = QPushButton("Merge Points")
        self.btn_merge_points.setCheckable(True)
        self.btn_merge_points.clicked.connect(self.toggle_merge_mode)
        panel_layout.addWidget(self.btn_merge_points)

        self.btn_clear = QPushButton("Clear Points")
        self.btn_clear.clicked.connect(self.clear_points_only)
        panel_layout.addWidget(self.btn_clear)

        self.btn_grid = QPushButton("Configure Grid")
        self.btn_grid.clicked.connect(self.open_grid_settings)
        panel_layout.addWidget(self.btn_grid)

        # Add-compass button
        self.btn_add_compass = QPushButton("Add Compass")
        self.btn_add_compass.clicked.connect(self.add_compass_to_map)
        panel_layout.addWidget(self.btn_add_compass)

        self.btn_export = QPushButton("Export (PNG, PDF, CSV, JSON...)")
        self.btn_export.clicked.connect(self.export_data)
        self.btn_export.setStyleSheet("font-weight: bold; background-color: #171817;")
        panel_layout.addWidget(self.btn_export)

        self.lbl_status = QLabel("Load a map image to get started.")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-weight: bold; color: #f8f9fa; margin-top: 10px;")
        panel_layout.addWidget(self.lbl_status)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("background-color: #ffffff; border: 1px solid #ced4da;")
        panel_layout.addWidget(self.info_text)

        layout.addWidget(right_panel, stretch=1)
        self.setCentralWidget(main_widget)


    def toggle_merge_mode(self, checked: bool):
        """Enables or disables the two-point merge mode."""
        if not self.view.scene.items():
            QMessageBox.warning(self, "Error", "Load a map first!")
            self.btn_merge_points.setChecked(False)
            return

        if checked:
            # Turn off other modes for safety
            self.btn_toggle_points.setChecked(False)
            self.view._merge_source = None
            self.view.mode = "MERGE"
            self.set_status("Mode: Merge. Click the first point, then the second.")
            self.btn_merge_points.setStyleSheet("background-color: #e63946; color: white; font-weight: bold;")
        else:
            self.view.mode = "IDLE"
            self.view._merge_source = None
            self.set_status("Mode: View. Merge canceled.")
            self.btn_merge_points.setStyleSheet("")

    def choose_line_color(self):
        """Opens the palette to choose the color for the next segments."""
        color = QColorDialog.getColor(
            self.view.current_line_color, self, "Choose the color for new lines"
        )
        if color.isValid():
            self.view.current_line_color = color

            # Apply the auto-break setting[cite: 1]
            if self.auto_break_on_color_change:
                self.view.start_new_line()
                self.set_status("Color changed. Click to start drawing a new line.")
            else:
                self.set_status("Color changed. The next segment will continue the current line.")

    def set_status(self, text: str):
        self.lbl_status.setText(text)

    def render_pdf_to_pixmap(self, pdf_path: str) -> QPixmap:
        """Renders a PDF page with automatic resolution limiting."""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                QMessageBox.warning(self, "Error", "The PDF file is empty.")
                return None

            page_num = 0
            if len(doc) > 1:
                page_num, ok = QInputDialog.getInt(
                    self,
                    "Select Page",
                    f"The document has {len(doc)} pages. Enter the page number (1-{len(doc)}):",
                    value=1,
                    min=1,
                    max=len(doc)
                )
                if not ok:
                    return None
                page_num -= 1

            page = doc[page_num]

            # --- START AUTOMATIC DPI FITTING ---
            # Set the desired max side in pixels (4096 for stability, 8192 for ultra-sharpness)
            max_side_target = self.pdf_max_resolution  # <-- Dynamic variable
            rect = page.rect  # Original page size in points[cite: 1]
            max_pdf_side = max(rect.width, rect.height)

            # Compute the optimal DPI: no more than 300, but so the image doesn't exceed max_side_target
            target_dpi = min(300, max(72, int((max_side_target / max_pdf_side) * 72)))

            zoom = target_dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            # --- END AUTOMATIC DPI FITTING ---

            qimg = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QImage.Format.Format_RGB888
            )
            return QPixmap.fromImage(qimg)

        except Exception as e:
            QMessageBox.critical(self, "PDF Read Error", f"Failed to open the PDF:\n{str(e)}")
            return None

    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a map or PDF document",
            "",
            IMAGE_FILE_FILTER,
        )
        if not file_path:
            return

        if not is_image_file(file_path):
            QMessageBox.warning(
                self,
                "Error",
                "Unsupported file format.",
            )
            return

        ext = os.path.splitext(file_path)[1].lower()
        pixmap = None

        # Load a PDF or a regular raster image
        if ext == ".pdf":
            pixmap = self.render_pdf_to_pixmap(file_path)
        else:
            reader = QImageReader(file_path)
            if not reader.canRead():
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to read the image:\n{reader.errorString()}",
                )
                return
            pixmap = QPixmap(file_path)

        if pixmap is None or pixmap.isNull():
            return

        self.clear_all()
        self.view.scene.addPixmap(pixmap)
        self.view.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.view.centerOn(pixmap.width() / 2, pixmap.height() / 2)
        self.set_status("Map loaded. Set the scale or start placing measurement points.")


    def add_compass_to_map(self):
        """Adds a new compass at the center of the visible map area."""
        if not self.view.scene.items():
            QMessageBox.warning(self, "Error", "Load a map first!")
            return

        # Find the center of the current viewport
        center_point = self.view.mapToScene(self.view.viewport().rect().center())

        compass = CompassItem(x=center_point.x(), y=center_point.y(), radius=45, ray_length=2500)
        self.view.scene.addItem(compass)
        self.set_status("Compass added. Drag with left click, hold Alt+left click to rotate, right click to delete.")

    def start_calibration(self):
        if not self.view.scene.items():
            QMessageBox.warning(self, "Error", "Load an image first!")
            return

        self.btn_merge_points.setChecked(False)
        self.btn_merge_points.setStyleSheet("")
        self.view._merge_source = None

        # Deactivate the points button during calibration
        self.btn_toggle_points.setChecked(False)
        self.btn_toggle_points.setStyleSheet("")

        self.view.reset_calibration_state()
        self.view.mode = "CALIBRATE"
        self.set_status("Calibration mode: choose the first point of the reference segment.")

    def clear_points_only(self):
        for pt in self.view.points:
            self.view.scene.removeItem(pt)

        # Iterate over the dicts and remove the graphics item specifically via the "item" key
        for line_data in self.view.lines:
            self.view.scene.removeItem(line_data["item"])

        self.view.points.clear()
        self.view.lines.clear()

        # Reset the line-break flag when clearing
        if hasattr(self.view, '_break_line'):
            self.view._break_line = False

        self.view.reset_calibration_state()
        self.update_calculations()

    def toggle_points_mode(self, checked: bool):
        """Toggles point-placement mode with the mouse."""

        self.btn_merge_points.setChecked(False)
        self.btn_merge_points.setStyleSheet("")
        self.view._merge_source = None

        if not self.view.scene.items():
            QMessageBox.warning(self, "Error", "Load a map first!")
            self.btn_toggle_points.setChecked(False)
            return

        if checked:
            self.view.mode = "POINTS"
            self.set_status("Mode: Placing Points. Left-click on the map to take measurements.")
            self.btn_toggle_points.setStyleSheet("background-color: #457b9d; color: white; font-weight: bold;")
        else:
            self.view.mode = "IDLE"
            self.set_status("Mode: View. Point placement disabled.")
            self.btn_toggle_points.setStyleSheet("")

    def open_settings(self):
        """Opens the settings dialog and applies the chosen configuration."""
        dlg = SettingsDialog(self.auto_break_on_color_change, self.pdf_max_resolution, self)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            auto_break, pdf_res, screen_res = dlg.get_values()

            # Apply the boolean flags
            self.auto_break_on_color_change = auto_break
            self.pdf_max_resolution = pdf_res

            # Apply the physical window resolution
            if screen_res != "Don't change":
                width, height = map(int, screen_res.split("x"))
                self.resize(width, height)

            self.set_status("System settings updated successfully.")


    def clear_all(self):
        self.view.reset_calibration_state()
        self.view.scene.clear()
        self.view.points.clear()
        self.view.lines.clear()
        self.view.meters_per_pixel = None
        self.info_text.clear()

    def collect_export_data(self) -> dict:
        """Gathers data and groups continuous segments into separate lines (routes)."""
        out_unit = self.combo_output_unit.currentText()
        m_per_px = self.view.meters_per_pixel
        use_px = out_unit == "px (pixels)" or m_per_px is None

        routes = []
        current_route = []

        flat_segments = []
        total_px = 0.0
        total_unit = 0.0

        for i, line_data in enumerate(self.view.lines):
            p1 = line_data["p1"].scenePos()
            p2 = line_data["p2"].scenePos()

            dist_px = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
            total_px += dist_px

            dist_u = dist_px
            if not use_px:
                dist_m = dist_px * m_per_px
                dist_u = dist_m / UNIT_TO_METERS[out_unit]
                total_unit += dist_u

            p1_idx = self.view.points.index(line_data["p1"]) + 1
            p2_idx = self.view.points.index(line_data["p2"]) + 1

            segment_info = {
                "index": i + 1,
                "p1_idx": p1_idx,
                "p2_idx": p2_idx,
                "p1_x": p1.x(),
                "p1_y": p1.y(),
                "p2_x": p2.x(),
                "p2_y": p2.y(),
                "dist_px": dist_px,
                "dist_unit": dist_u,
            }

            flat_segments.append(segment_info)

            # Line-grouping logic
            if not current_route:
                current_route.append(segment_info)
            else:
                # If the first point of the current segment matches the second point of the previous one
                if current_route[-1]["p2_idx"] == p1_idx:
                    current_route.append(segment_info)
                else:
                    # Route break: save the old one and start a new one
                    routes.append(current_route)
                    current_route = [segment_info]

        # Add the last accumulated line
        if current_route:
            routes.append(current_route)

        return {
            "scene": self.view.scene,
            "unit": "px" if use_px else out_unit,
            "meters_per_pixel": m_per_px,
            "segments": flat_segments, # The flat list is kept for compatibility with CSVExporter
            "routes": routes,          # New grouped list for the UI
            "total_distance": total_px if use_px else total_unit,
        }

    def open_grid_settings(self):
        is_calibrated = self.view.meters_per_pixel is not None
        dlg = GridDialog(self.view.scene.grid_value, self.view.scene.grid_unit, is_calibrated, self)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            enabled, val, unit = dlg.get_values()

            self.view.scene.show_grid = enabled
            self.view.scene.grid_value = val
            self.view.scene.grid_unit = unit

            if enabled:
                if unit == "px (pixels)":
                    self.view.grid_step_px = val
                elif unit == "cm (on screen)":
                    # Standard calculation at 96 DPI: 1 inch = 2.54 cm = 96 px -> 1 cm ≈ 37.795 px
                    self.view.grid_step_px = val * 37.795
                else:
                    # Calculation for real-world units
                    meters = val * UNIT_TO_METERS[unit]
                    self.view.scene.grid_step_px = meters / self.view.meters_per_pixel

            self.view.scene.invalidate(self.view.scene.sceneRect(), QGraphicsScene.SceneLayer.ForegroundLayer)
            self.update_calculations()

    def update_calculations(self):
        m_per_px = self.view.meters_per_pixel
        text_color = getattr(self, "text_color_hex", "#a8dadc")

        if m_per_px is None:
            scale_info = "<b>SCALE:</b> Not set (output in px)"
        else:
            scale_info = (
                f"<b>SCALE:</b> 1 px = {m_per_px:.4f} m | 1 m = {1/m_per_px:.2f} px"
            )

        # FIX 1: Access the grid variables via self.view.scene
        grid_active = self.view.scene.show_grid and self.view.scene.grid_step_px > 0
        if grid_active:
            scale_info += f"<br><span style='color: #457b9d;'><b>GRID:</b> 1 cell = {self.view.scene.grid_value} {self.view.scene.grid_unit}</span>"

        if not self.view.lines:
            full_html = (
                f"<div style='color: {text_color}; font-family: sans-serif; font-size: 13px;'>"
                f"{scale_info}<hr>"
                f"Points placed: {len(self.view.points)}<br>"
                f"Connect at least 2 points to take measurements."
                f"</div>"
            )
            self.info_text.setHtml(full_html)
            return

        data = self.collect_export_data()
        unit_label = data["unit"]
        routes = data.get("routes", [])

        NUM_COLUMNS = 2
        routes_html = ""
        total_cells = 0.0

        # Iterate over each independent line
        for route_idx, route_segs in enumerate(routes):
            # Compute the length of this specific line
            route_dist_px = sum(seg["dist_px"] for seg in route_segs)
            route_dist = sum(seg["dist_unit"] for seg in route_segs)

            cells_info = ""
            if grid_active:
                route_cells = route_dist_px / self.view.scene.grid_step_px
                total_cells += route_cells
                cells_info = f" | <span style='color: #457b9d;'>{route_cells:.1f} cells</span>"

            # FIX 2: Restore {cells_info} in the line header
            routes_html += (
                f"<div style='margin-top: 12px; margin-bottom: 4px;'>"
                f"<b>Line {route_idx + 1}</b> "
                f"(Length: <span style='color: #d90429;'>{route_dist:.2f} {unit_label}</span>{cells_info})"
                f"</div>"
                f"<table style='width: 100%; border-collapse: collapse;'>"
            )

            # Build the segment table for the current line
            for i in range(0, len(route_segs), NUM_COLUMNS):
                row_segs = route_segs[i : i + NUM_COLUMNS]
                routes_html += "<tr>"

                for seg in row_segs:
                    p1_num = seg["p1_idx"]
                    p2_num = seg["p2_idx"]
                    dist_val = seg["dist_unit"]

                    # FIX 3: Compute and output {seg_cells_html} for each individual segment
                    seg_cells_html = ""
                    if grid_active:
                        seg_cells = seg["dist_px"] / self.view.scene.grid_step_px
                        seg_cells_html = f" | <b>{seg_cells:.1f} cells</b>"

                    routes_html += (
                        f"<td style='padding: 3px 8px; border: 1px solid #444444; background-color: #ffffff; color: #000000;'>"
                        f"• <b>{p1_num}➔{p2_num}:</b> {dist_val:.2f} {unit_label}{seg_cells_html}"
                        f"</td>"
                    )

                if len(row_segs) < NUM_COLUMNS:
                    for _ in range(NUM_COLUMNS - len(row_segs)):
                        routes_html += "<td style='border: none;'></td>"

                routes_html += "</tr>"

            routes_html += "</table>"

        # Grand total across all lines
        total_cells_html = ""
        if grid_active:
            total_cells_html = f" / <span style='color: #457b9d;'>{total_cells:.1f} cells</span>"

        total_info = (
            f"<b>TOTAL LENGTH OF ALL LINES:</b> "
            f"<span style='font-size: 14px;'><b>{data['total_distance']:.3f} {unit_label}</b>{total_cells_html}</span>"
        )

        full_html = (
            f"<div style='color: {text_color}; font-family: sans-serif; font-size: 12px; line-height: 1.3;'>"
            f"{scale_info}"
            f"<hr style='margin: 6px 0;'>"
            f"<b>DETAILS:</b>"
            f"{routes_html}"
            f"<hr style='margin: 10px 0 6px 0;'>"
            f"{total_info}"
            f"</div>"
        )

        self.info_text.setHtml(full_html)

    def export_data(self):
        """Exports the map, rendering the text directly onto the scene."""
        if not self.view.scene.items():
            QMessageBox.warning(self, "Error", "No data to export!")
            return

        filters = self.export_manager.get_file_filters()
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Result", "result", filters
        )
        if not file_path:
            return

        # 1. Ask for the text color
        color = QColorDialog.getColor(QColor(self.text_color_hex), self, "Choose the text color")
        if not color.isValid():
            return

        export_text_color = color.name()

        # Temporarily save the current UI text color and set the chosen one
        old_color = self.text_color_hex
        self.text_color_hex = export_text_color
        self.update_calculations()  # Regenerate the HTML with the new color

        # 2. Grab the updated HTML
        html_content = self.info_text.toHtml()

        # 3. Create a text overlay
        text_item = QGraphicsTextItem()
        text_item.setHtml(
            f'<div style="background-color: rgba(255, 255, 255, 0.9); '
            f'padding: 10px; border-radius: 5px; '
            f'font-family: sans-serif;">'
            f'{html_content}'
            f'</div>'
        )

        # Place it in the corner of the scene
        text_item.setPos(10, 10)
        text_item.setZValue(999)  # Above the map and lines
        self.view.scene.addItem(text_item)

        # 4. Save to file
        data = self.collect_export_data()
        try:
            success = self.export_manager.export(file_path, selected_filter, data)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            success = False
        finally:
            # 5. Always remove the overlay and restore the original color in the program window
            self.view.scene.removeItem(text_item)
            self.text_color_hex = old_color
            self.update_calculations()

        if success:
            QMessageBox.information(self, "Success", f"File saved:\n{file_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
