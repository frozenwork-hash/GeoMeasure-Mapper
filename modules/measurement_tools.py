import math
from PyQt6.QtCore import Qt, QPointF, QRectF, QObject, pyqtSignal
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath, QFont, QPolygonF
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem, QInputDialog, QGraphicsLineItem, QGraphicsPolygonItem

def ramer_douglas_peucker(points: list[QPointF], epsilon: float) -> list[QPointF]:
    if len(points) < 3:
        return points
    dmax, index, end = 0.0, 0, len(points) - 1
    p1, p2 = points[0], points[end]
    dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
    norm = math.hypot(dx, dy)

    for i in range(1, end):
        p = points[i]
        dist = math.hypot(p.x() - p1.x(), p.y() - p1.y()) if norm == 0 else abs(dy * p.x() - dx * p.y() + p2.x() * p1.y() - p2.y() * p1.x()) / norm
        if dist > dmax:
            index, dmax = i, dist

    if dmax > epsilon:
        r1 = ramer_douglas_peucker(points[:index + 1], epsilon)
        r2 = ramer_douglas_peucker(points[index:], epsilon)
        return r1[:-1] + r2
    return [points[0], points[end]]

def shoelace_area_px(points: list[QPointF]) -> float:
    n = len(points)
    if n < 3:
        return 0.0
    area = sum(points[i].x() * points[(i + 1) % n].y() - points[(i + 1) % n].x() * points[i].y() for i in range(n))
    return abs(area) / 2.0

class BaseTool(QObject):
    finished = pyqtSignal(dict)
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.scene = view.scene() if callable(view.scene) else view.scene

    def get_scale_factor(self) -> float:
        """Returns the number of real-world units per scene pixel (defined by the ruler)."""
        mpp = getattr(self.view, "meters_per_pixel", None)
        if mpp is None:
            return 1.0

        unit_name = self.get_unit_name()
        if unit_name in ("px", "px (pixels)"):
            return 1.0
        
        # Import UnitManager to convert meters to the required unit of measurement
        from unit_manager import UnitManager
        units = UnitManager.get_units()
        if unit_name in units:
            # Math: (meters / pixel) / (meters / unit) = units / pixel
            return mpp / units[unit_name]
            
        return 1.0

    def get_unit_name(self) -> str:
        """Returns the current units of measurement (set by the ruler)."""
        if hasattr(self.view, "main_window") and self.view.main_window:
            return self.view.main_window.combo_output_unit.currentText()
        return "px"

    def mousePress(self, event, scene_pos: QPointF): pass
    def mouseMove(self, event, scene_pos: QPointF): pass
    def mouseRelease(self, event, scene_pos: QPointF): pass
    def doubleClick(self, event, scene_pos: QPointF): pass
    def keyPress(self, event): pass
    def cancel(self): pass

    def create_label(self, text: str, pos: QPointF, color: QColor, parent_item=None) -> QGraphicsTextItem:
        label_item = QGraphicsTextItem(text, parent_item)
        label_item.setDefaultTextColor(color)
        label_item.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
        label_item.setPos(pos)
        
        show_labels = getattr(self.view, "show_measurement_labels", True)
        label_item.setVisible(show_labels)
        
        if parent_item is None:
            self.scene.addItem(label_item)
            
        return label_item

class ShapeTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.center_point = None
        self.preview_item = None

    def mousePress(self, event, scene_pos: QPointF):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        event.accept()

        if self.center_point is None:
            self.center_point = scene_pos
        else:
            self._create_shape(scene_pos)
            self.cancel()

    def mouseMove(self, event, scene_pos: QPointF):
        if self.center_point is None:
            return
        event.accept()
        
        radius = math.hypot(scene_pos.x() - self.center_point.x(), scene_pos.y() - self.center_point.y())
        path = QPainterPath()
        path.addEllipse(self.center_point, radius, radius)

        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            self.preview_item.setPen(QPen(QColor(0, 150, 255), 2, Qt.PenStyle.DashLine))
            self.scene.addItem(self.preview_item)
        self.preview_item.setPath(path)

    def _create_shape(self, edge_pos: QPointF):
        shape_type, ok = QInputDialog.getItem(
            None, "Select Shape", "Shape Type:", ["Circle", "Square", "Regular Polygon"], 0, False
        )
        if not ok:
            return

        

        radius = math.hypot(edge_pos.x() - self.center_point.x(), edge_pos.y() - self.center_point.y())
        points = []

        if shape_type == "Circle":
            path = QPainterPath()
            path.addEllipse(self.center_point, radius, radius)
            area_px = math.pi * (radius ** 2)
            center_x, center_y = self.center_point.x(), self.center_point.y()
        else:
            n_sides = 4
            if shape_type == "Regular Polygon":
                n_sides, ok = QInputDialog.getInt(None, "Polygon Sides", "Enter number of sides (3-36):", 5, 3, 36)
                if not ok:
                    return

            angle_step = (2 * math.pi) / n_sides
            start_angle = math.atan2(edge_pos.y() - self.center_point.y(), edge_pos.x() - self.center_point.x())

            for i in range(n_sides):
                a = start_angle + i * angle_step
                points.append(QPointF(self.center_point.x() + radius * math.cos(a), self.center_point.y() + radius * math.sin(a)))

            path = QPainterPath()
            path.moveTo(points[0])
            for p in points[1:]:
                path.lineTo(p)
            path.closeSubpath()
            area_px = shoelace_area_px(points)
            center_x = sum(p.x() for p in points) / len(points)
            center_y = sum(p.y() for p in points) / len(points)

        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(0, 150, 255), 2.5))
        item.setBrush(QBrush(QColor(0, 150, 255, 50)))
        self.scene.addItem(item)

        scale = self.get_scale_factor()
        unit = self.get_unit_name()
        real_area = area_px * (scale ** 2)

        label_item = self.create_label(f"{real_area:.2f} {unit}²", QPointF(center_x - 20, center_y - 10), QColor(0, 100, 200), item)

        data = {"type": shape_type, "area": real_area, "unit": unit, "ui_item": item, "ui_label": label_item}
       
        if shape_type == "Circle":
            data["center"] = (center_x, center_y)
            data["radius"] = radius
        else:
            data["points"] = [(p.x(), p.y()) for p in points]
        
        if not hasattr(self.view, "polygons"):
            self.view.polygons = []
        self.view.polygons.append(data)
        self.finished.emit(data)

    def cancel(self):
        self.center_point = None
        if self.preview_item and self.preview_item.scene():
            self.scene.removeItem(self.preview_item)
            self.preview_item = None


class AreaTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.drawing_points = []
        self.preview_item = None

    def mousePress(self, event, scene_pos: QPointF):
        if event.button() == Qt.MouseButton.RightButton:
            if len(self.drawing_points) >= 3:
                self.close_polygon()
                event.accept() # Событие перехвачено, карта не сдвинется
            else:
                event.ignore() # Если точек мало, отдаем ПКМ для перемещения карты
            return

        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        event.accept()

        if not self.drawing_points and self._try_select_existing_line(scene_pos):
            return
        self.drawing_points.append(scene_pos)

    def doubleClick(self, event, scene_pos: QPointF):
        if event.button() == Qt.MouseButton.LeftButton:
            self.close_polygon()
            event.accept()
        else:
            event.ignore()

    def _try_select_existing_line(self, pos: QPointF) -> bool:
        from PyQt6.QtCore import QRectF
        from PyQt6.QtWidgets import QGraphicsLineItem
        import math

        rect = QRectF(pos.x() - 10, pos.y() - 10, 20, 20)
        items = self.scene.items(rect)
        line_items = [it for it in items if isinstance(it, QGraphicsLineItem)]

        if not line_items:
            return False

        if hasattr(self.view, "lines") and self.view.lines:
            pts = []
            for ld in self.view.lines:
                if "p1" in ld and "p2" in ld:
                    p1_pos = ld["p1"].scenePos()
                    p2_pos = ld["p2"].scenePos()
                    
                    # Записываем точки, избегая дублирования на стыках отрезков
                    if not pts or math.hypot(pts[-1].x() - p1_pos.x(), pts[-1].y() - p1_pos.y()) > 1.0:
                        pts.append(p1_pos)
                    if math.hypot(pts[-1].x() - p2_pos.x(), pts[-1].y() - p2_pos.y()) > 1.0:
                        pts.append(p2_pos)

            # Проверяем, что точек достаточно (минимум треугольник) и контур замкнут
            if len(pts) >= 3 and math.hypot(pts[0].x() - pts[-1].x(), pts[0].y() - pts[-1].y()) < 15.0:
                # Передаем собранные точки нашему монолитному методу, 
                # который корректно всё посчитает, нарисует и выдаст текст
                self.drawing_points = pts
                self.close_polygon()
                return True
                
        return False

    def mouseMove(self, event, scene_pos: QPointF):
        if not self.drawing_points:
            return
        event.accept()
        pts = self.drawing_points + [scene_pos]
        path = QPainterPath()
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        
        # Визуально замыкаем фигуру, если точек больше двух
        if len(pts) > 2:
            path.closeSubpath()
            
        if not self.preview_item:
            self.preview_item = QGraphicsPathItem()
            self.preview_item.setPen(QPen(QColor(255, 140, 0), 2, Qt.PenStyle.DashLine))
            self.preview_item.setBrush(QBrush(QColor(255, 140, 0, 30)))
            self.scene.addItem(self.preview_item)
        self.preview_item.setPath(path)

    def keyPress(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.close_polygon()

    def close_polygon(self):
        if not self.drawing_points:
            return

        if len(self.drawing_points) > 1:
            dist = math.hypot(self.drawing_points[0].x() - self.drawing_points[-1].x(),
                              self.drawing_points[0].y() - self.drawing_points[-1].y())
            if dist < 1e-5:
                self.drawing_points.pop()

        if len(self.drawing_points) < 3:
            return


        points = list(self.drawing_points)
        self.cancel()

        path = QPainterPath()
        path.moveTo(points[0])
        for p in points[1:]:
            path.lineTo(p)
        path.closeSubpath()

        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(255, 140, 0), 2.5))
        item.setBrush(QBrush(QColor(255, 140, 0, 60)))
        self.scene.addItem(item)

        area_px = shoelace_area_px(points)
        scale = self.get_scale_factor()
        unit = self.get_unit_name()
        real_area = area_px * (scale ** 2)

        area_val = self.calculate_area(points) * (scale ** 2)
        perimeter_val = self.calculate_perimeter(points) * scale

        center_x = sum(p.x() for p in points) / len(points)
        center_y = sum(p.y() for p in points) / len(points)

        label_text = f"S: {real_area:.2f} {unit}²\nP: {perimeter_val:.2f} {unit}"
        label_item = self.create_label(f"{real_area:.2f} {unit}²", QPointF(center_x - 20, center_y - 10), QColor(200, 80, 0), item)

        poly_data = {
            "type": "drawn_polygon", 
            "points": [(p.x(), p.y()) for p in points], 
            "area": real_area, 
            "unit": unit,
            "ui_item": item, 
            "ui_label": label_item
        }
        
        if not hasattr(self.view, 'polygons'):
            self.view.polygons = []
        self.view.polygons.append(poly_data)

    def cancel(self):
        self.drawing_points.clear()
        if self.preview_item and self.preview_item.scene():
            self.scene.removeItem(self.preview_item)
            self.preview_item = None

    def calculate_area(self, points):
        area = 0.0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            area += points[i].x() * points[j].y()
            area -= points[j].x() * points[i].y()
        return abs(area) / 2.0

    def calculate_perimeter(self, points):
        peri = 0.0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            peri += math.hypot(points[i].x() - points[j].x(), points[i].y() - points[j].y())
        return peri


class AngleTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.points = []
        self.temp_item = None
        self.lines = []

    def mousePress(self, event, scene_pos: QPointF):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        event.accept()
        self.points.append(scene_pos)
        
        if len(self.points) == 3:
            self._calculate_and_draw()
            self._cleanup_temp()
        else:
            self._update_preview()

    def mouseMove(self, event, scene_pos: QPointF):
        if not self.points:
            return
        event.accept()
        pts = self.points + [scene_pos]
        path = QPainterPath()
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
            
        if not self.temp_item:
            self.temp_item = QGraphicsPathItem()
            self.temp_item.setPen(QPen(QColor(153, 50, 204), 2, Qt.PenStyle.DashLine))
            self.scene.addItem(self.temp_item)
        self.temp_item.setPath(path)

    def _update_preview(self):
        for line in self.lines:
            if line.scene():
                self.scene.removeItem(line)
        self.lines.clear()
        
        if len(self.points) > 1:
            line = self.scene.addLine(self.points[0].x(), self.points[0].y(), self.points[1].x(), self.points[1].y(), QPen(QColor(153, 50, 204), 2))
            self.lines.append(line)

    def _calculate_and_draw(self):
        v, p1, p2 = self.points[1], self.points[0], self.points[2]
        
        ang1 = math.degrees(math.atan2(p1.y() - v.y(), p1.x() - v.x()))
        ang2 = math.degrees(math.atan2(p2.y() - v.y(), p2.x() - v.x()))
        
        diff_deg = (ang2 - ang1) % 360.0
        
        if diff_deg > 180.0:
            diff_deg -= 360.0
            
        path = QPainterPath()
        path.moveTo(v)
        path.arcTo(QRectF(v.x() - 30, v.y() - 30, 60, 60), -ang1, -diff_deg)
        path.closeSubpath()

        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(153, 50, 204), 2))
        item.setBrush(QBrush(QColor(153, 50, 204, 60)))
        self.scene.addItem(item)
        
        line1 = self.scene.addLine(p1.x(), p1.y(), v.x(), v.y(), QPen(QColor(153, 50, 204), 2))
        line2 = self.scene.addLine(v.x(), v.y(), p2.x(), p2.y(), QPen(QColor(153, 50, 204), 2))

        label_item = self.create_label(f"{abs(diff_deg):.1f}°", QPointF(v.x() + 10, v.y() + 10), QColor(120, 20, 180), item)

        angle_data = {
            "points": [(p.x(), p.y()) for p in self.points], 
            "degrees": abs(diff_deg), 
            "ui_item": item, 
            "ui_label": label_item,
            "ui_lines": [line1, line2]
        }
        
        if not hasattr(self.view, "angles"):
            self.view.angles = []
        self.view.angles.append(angle_data)
        self.finished.emit(angle_data)

    def _cleanup_temp(self):
        self.points.clear()
        if self.temp_item and self.temp_item.scene():
            self.scene.removeItem(self.temp_item)
            self.temp_item = None
        for line in self.lines:
            if line.scene():
                self.scene.removeItem(line)
        self.lines.clear()

    def cancel(self):
        self._cleanup_temp()


class FreehandTool(BaseTool):
    def __init__(self, view):
        super().__init__(view)
        self.is_drawing = False
        self.points = []
        self.preview_item = None

    def mousePress(self, event, scene_pos: QPointF):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        event.accept()
        self.is_drawing = True
        self.points = [scene_pos]

    def mouseMove(self, event, scene_pos: QPointF):
        if self.is_drawing:
            event.accept()
            self.points.append(scene_pos)
            path = QPainterPath()
            path.moveTo(self.points[0])
            for p in self.points[1:]:
                path.lineTo(p)
            if not self.preview_item:
                self.preview_item = QGraphicsPathItem()
                self.preview_item.setPen(QPen(QColor(220, 20, 60), 2))
                self.scene.addItem(self.preview_item)
            self.preview_item.setPath(path)

    def mouseRelease(self, event, scene_pos: QPointF):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            event.accept()
            self.is_drawing = False
            if self.preview_item and self.preview_item.scene():
                self.scene.removeItem(self.preview_item)
                self.preview_item = None
            if len(self.points) > 2:
                simplified = ramer_douglas_peucker(self.points, epsilon=2.0)
                self._save(simplified)
            self.points.clear()

    def _save(self, points):
        path = QPainterPath()
        path.moveTo(points[0])
        total_len_px = 0.0
        for i in range(1, len(points)):
            path.lineTo(points[i])
            total_len_px += math.hypot(points[i].x() - points[i-1].x(), points[i].y() - points[i-1].y())
            
        item = QGraphicsPathItem(path)
        item.setPen(QPen(QColor(220, 20, 60), 2))
        self.scene.addItem(item)
        
        scale = self.get_scale_factor()
        unit = self.get_unit_name()
        real_length = total_len_px * scale

        mid = points[len(points)//2]
        label_item = self.create_label(f"{real_length:.2f} {unit}", mid, QColor(180, 0, 30), item)

        data = {
            "points": [(p.x(), p.y()) for p in points], 
            "length": real_length,
            "unit": unit,
            "ui_item": item, 
            "ui_label": label_item
        }
        
        if not hasattr(self.view, "freehand_lines"):
            self.view.freehand_lines = []
        self.view.freehand_lines.append(data)
        self.finished.emit(data)
        
    def cancel(self):
        self.is_drawing = False
        self.points.clear()
        if self.preview_item and self.preview_item.scene():
            self.scene.removeItem(self.preview_item)
            self.preview_item = None