import numpy as np
from PyQt6.QtCore import QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QMenu,
    QRubberBand,
)

from models.field import ExposureField
from models.mark import AlignmentMark


class ExposureCanvas(QGraphicsView):
    field_clicked = pyqtSignal(object)
    mark_clicked = pyqtSignal(object)
    mark_selected = pyqtSignal(str)
    mouse_moved = pyqtSignal(float, float)
    mark_picked = pyqtSignal(str, float, float)
    mark_add_requested = pyqtSignal(float, float)
    mark_delete_requested = pyqtSignal(str)
    zoom_changed = pyqtSignal(int)

    COLORS = {
        "field": QColor(70, 130, 200),
        "field_sel": QColor(255, 215, 0),
        "grid": QColor(200, 200, 200),
        "grid_major": QColor(180, 180, 180),
        "bg": QColor(245, 245, 245),
        "link": QColor(200, 100, 50, 150),
        "crosshair": QColor(0, 150, 0),
    }

    GRID_STEP = 0.5
    GRID_MAJOR_EVERY = 5
    GRID_EXTENT = 500
    MIN_ZOOM_RATIO = 0.10
    MAX_ZOOM_RATIO = 50.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setBackgroundBrush(QBrush(self.COLORS["bg"]))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setToolTip(
            "Drag to pan, use the scrollbars, or select Zoom Area and drag a rectangle. "
            "The mouse wheel also changes magnification."
        )
        self._fields: list[ExposureField] = []
        self._marks: list[AlignmentMark] = []
        self._field_items: dict[str, QGraphicsItem] = {}
        self._mark_items: dict[str, QGraphicsItem] = {}
        self._link_items: list[QGraphicsItem] = []
        self._gds_items: list[QGraphicsItem] = []
        self._selected_field: str | None = None
        self._selected_mark: str | None = None
        self._field_size: float = 0.6
        self._gds_polygons: list[np.ndarray] = []
        self._gds_layer: tuple[int, int] | int | None = None
        self._assignment_mode = False
        self._pick_mode: bool = False
        self._pick_threshold_mm: float = 0.5
        self._shift_held: bool = False
        self._enabled_fields: set[str] | None = None
        self._navigation_mode = "pan"
        self._zoom_origin = None
        self._rubber_band: QRubberBand | None = None
        self._fit_scale = 1.0

        self._draw_grid()
        self._fit_view()

    @property
    def navigation_mode(self) -> str:
        return self._navigation_mode

    def set_navigation_mode(self, mode: str):
        if mode not in {"pan", "zoom_area"}:
            raise ValueError(f"Unsupported navigation mode: {mode}.")
        self._cancel_zoom_drag()
        self._navigation_mode = mode
        self._apply_pick_mode()

    def set_field_size(self, field_size: float):
        if not np.isfinite(field_size) or field_size <= 0:
            raise ValueError("Field size must be positive.")
        self._field_size = field_size

    def set_fields(self, fields: list[ExposureField]):
        self._fields = fields

    def set_enabled_fields(self, enabled: set[str] | None):
        self._enabled_fields = enabled

    def set_marks(self, marks: list[AlignmentMark]):
        self._marks = marks

    def set_selected_field(self, name: str | None):
        self._selected_field = name

    def set_assignment_mode(self, active: bool):
        self._assignment_mode = active
        self._apply_pick_mode()

    def set_selected_mark(self, mark_id: str | None):
        self._selected_mark = mark_id

    def refresh(self, keep_view=False):
        self._clear_dynamic()
        for draw_fn in (self._draw_gds_polygons, self._draw_links, self._draw_fields, self._draw_marks):
            try:
                draw_fn()
            except Exception:
                pass
        if keep_view:
            self._update_scene_rect()
            self._emit_zoom_changed()
        else:
            try:
                self._fit_view()
            except Exception:
                default_rect = QRectF(-0.5, -0.5, 5, 5)
                self._scene.setSceneRect(default_rect)
                self.fitInView(default_rect, Qt.AspectRatioMode.KeepAspectRatio)
                self._fit_scale = max(abs(self.transform().m11()), 1e-12)
                self._emit_zoom_changed()

    def _clear_dynamic(self):
        for item in self._field_items.values():
            self._scene.removeItem(item)
        self._field_items.clear()
        for item in self._mark_items.values():
            self._scene.removeItem(item)
        self._mark_items.clear()
        for item in self._link_items:
            self._scene.removeItem(item)
        self._link_items.clear()
        for item in self._gds_items:
            self._scene.removeItem(item)
        self._gds_items.clear()

    def fit_all(self):
        self._fit_view()

    def _content_rect(self) -> QRectF:
        rects = []
        hs = self._field_size / 2
        for field in self._fields:
            if (
                self._enabled_fields is not None
                and field.name not in self._enabled_fields
            ):
                continue
            rects.append(
                QRectF(
                    field.center_x - hs,
                    field.center_y - hs,
                    self._field_size,
                    self._field_size,
                )
            )
        for mark in self._marks:
            rects.append(
                QRectF(mark.center_x - 0.15, mark.center_y - 0.15, 0.3, 0.3)
            )
        for vertices in self._gds_polygons:
            if len(vertices) == 0 or not np.isfinite(vertices).all():
                continue
            xmin, ymin = np.min(vertices, axis=0)
            xmax, ymax = np.max(vertices, axis=0)
            rects.append(
                QRectF(
                    float(xmin),
                    float(ymin),
                    float(xmax - xmin),
                    float(ymax - ymin),
                )
            )
        if not rects:
            return QRectF(-0.5, -0.5, 5, 5)

        xmin = min(rect.left() for rect in rects)
        xmax = max(rect.right() for rect in rects)
        ymin = min(rect.top() for rect in rects)
        ymax = max(rect.bottom() for rect in rects)
        span = max(xmax - xmin, ymax - ymin)
        margin = max(span * 0.15 if span > 0 else 1.0, 2.0)
        rect = QRectF(
            xmin - margin,
            ymin - margin,
            xmax - xmin + 2 * margin,
            ymax - ymin + 2 * margin,
        )
        if rect.width() > 10000 or rect.height() > 10000:
            return QRectF(-5000, -5000, 10000, 10000)
        return rect

    def _update_scene_rect(self) -> QRectF:
        rect = self._content_rect()
        self._scene.setSceneRect(rect)
        return rect

    def _fit_view(self):
        rect = self._update_scene_rect()
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._fit_scale = max(abs(self.transform().m11()), 1e-12)
        self._emit_zoom_changed()

    def _zoom_ratio(self) -> float:
        return abs(self.transform().m11()) / max(self._fit_scale, 1e-12)

    def _emit_zoom_changed(self):
        self.zoom_changed.emit(max(1, round(self._zoom_ratio() * 100)))

    def _zoom_by(self, factor: float, *, under_mouse: bool = False):
        if not np.isfinite(factor) or factor <= 0:
            return
        current_ratio = self._zoom_ratio()
        target_ratio = min(
            self.MAX_ZOOM_RATIO,
            max(self.MIN_ZOOM_RATIO, current_ratio * factor),
        )
        applied_factor = target_ratio / current_ratio
        if abs(applied_factor - 1.0) < 1e-9:
            return

        previous_anchor = self.transformationAnchor()
        anchor = (
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
            if under_mouse
            else QGraphicsView.ViewportAnchor.AnchorViewCenter
        )
        self.setTransformationAnchor(anchor)
        self.scale(applied_factor, applied_factor)
        self.setTransformationAnchor(previous_anchor)
        self._emit_zoom_changed()

    def zoom_in(self):
        self._zoom_by(1.25)

    def zoom_out(self):
        self._zoom_by(1 / 1.25)

    def _zoom_to_viewport_rect(self, viewport_rect: QRect):
        if viewport_rect.width() < 8 or viewport_rect.height() < 8:
            self._zoom_by(1.5, under_mouse=True)
            return

        scene_rect = self.mapToScene(viewport_rect).boundingRect()
        if not scene_rect.isValid() or scene_rect.isEmpty():
            return
        self.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
        ratio = self._zoom_ratio()
        if ratio > self.MAX_ZOOM_RATIO:
            correction = self.MAX_ZOOM_RATIO / ratio
            self.scale(correction, correction)
        elif ratio < self.MIN_ZOOM_RATIO:
            correction = self.MIN_ZOOM_RATIO / ratio
            self.scale(correction, correction)
        self._emit_zoom_changed()

    def _cancel_zoom_drag(self):
        if self._rubber_band is not None:
            self._rubber_band.hide()
        self._zoom_origin = None

    def _draw_grid(self):
        pen_minor = QPen(self.COLORS["grid"], 0)
        pen_minor.setStyle(Qt.PenStyle.DashLine)
        pen_major = QPen(self.COLORS["grid_major"], 0)
        pen_major.setStyle(Qt.PenStyle.DashLine)

        step = self.GRID_STEP
        major_every = self.GRID_MAJOR_EVERY
        ext = self.GRID_EXTENT

        n = int(ext / step)
        for i in range(-n, n + 1):
            pos = i * step
            is_major = i % major_every == 0
            pen = pen_major if is_major else pen_minor
            self._scene.addLine(pos, -ext, pos, ext, pen)
            self._scene.addLine(-ext, pos, ext, pos, pen)

    def _draw_fields(self):
        no_brush = QBrush(Qt.BrushStyle.NoBrush)
        font = QFont("Arial", 12)
        for f in self._fields:
            if self._enabled_fields is not None and f.name not in self._enabled_fields:
                continue
            hs = self._field_size / 2
            rect = QRectF(f.center_x - hs, f.center_y - hs,
                          self._field_size, self._field_size)
            is_sel = f.name == self._selected_field
            color = self.COLORS["field_sel" if is_sel else "field"]
            pen = QPen(color, 0)
            item = self._scene.addRect(rect, pen, no_brush)
            item.setData(0, f.name)
            item.setData(1, "field")
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._field_items[f.name] = item
            dot = self._scene.addEllipse(
                f.center_x - 0.05, f.center_y - 0.05,
                0.1, 0.1, QPen(Qt.PenStyle.NoPen), QBrush(color))
            dot.setData(0, f.name)
            dot.setData(1, "field")
            self._field_items[f.name + "_dot"] = dot
            txt = self._scene.addText(str(f.index), font)
            r = txt.boundingRect()
            desired_h = self._field_size * 0.05
            s = desired_h / r.height() if r.height() > 0 else 0.01
            txt.setScale(s)
            txt.setPos(
                f.center_x - r.width() * s / 2,
                f.center_y - r.height() * s / 2
            )
            txt.setDefaultTextColor(color)
            self._field_items[f.name + "_txt"] = txt

    def _draw_marks(self):
        for m in self._marks:
            cx, cy = m.center_x, m.center_y
            is_sel = m.mark_id == self._selected_mark
            color = self.COLORS["crosshair"] if not is_sel else QColor(0, 255, 0)
            pen = QPen(color, 0)
            line_h = self._scene.addLine(cx - 0.15, cy, cx + 0.15, cy, pen)
            line_h.setData(0, m.mark_id)
            line_h.setData(1, "mark")
            line_h.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._mark_items[m.mark_id] = line_h
            line_v = self._scene.addLine(cx, cy - 0.15, cx, cy + 0.15, pen)
            line_v.setData(0, m.mark_id)
            line_v.setData(1, "mark")
            line_v.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self._mark_items[m.mark_id + "_v"] = line_v

    def _draw_links(self):
        for f in self._fields:
            if self._enabled_fields is not None and f.name not in self._enabled_fields:
                continue
            if f.mark_id:
                mark = self._find_mark(f.mark_id)
                if not mark:
                    continue
                dx = f.center_x - mark.center_x
                dy = f.center_y - mark.center_y
                d = (dx * dx + dy * dy) ** 0.5
                if d > 1000.0:
                    continue
                pen = QPen(self.COLORS["link"], 0)
                pen.setStyle(Qt.PenStyle.DashLine)
                line = self._scene.addLine(
                    f.center_x, f.center_y,
                    mark.center_x, mark.center_y, pen
                )
                self._link_items.append(line)

    @staticmethod
    def _next_mark_id(marks: list[AlignmentMark]) -> str:
        max_n = 0
        for m in marks:
            if m.mark_id.startswith("PICK_"):
                try:
                    n = int(m.mark_id.split("_", 1)[1])
                    if n > max_n:
                        max_n = n
                except ValueError:
                    pass
        return f"PICK_{max_n + 1}"

    def _find_mark(self, mark_id: str) -> AlignmentMark | None:
        for m in self._marks:
            if m.mark_id == mark_id:
                return m
        return None

    def _find_mark_at(self, x: float, y: float) -> str | None:
        """Return mark_id if click is near a mark crosshair center."""
        nearest_id = None
        nearest_distance = 0.2
        for mark in self._marks:
            distance = ((mark.center_x - x) ** 2 + (mark.center_y - y) ** 2) ** 0.5
            if distance <= nearest_distance:
                nearest_distance = distance
                nearest_id = mark.mark_id
        return nearest_id

    def set_gds_layer(
        self, layer: tuple[int, int] | int | None, polygons: list[np.ndarray] | None = None
    ):
        self._gds_layer = layer
        self._gds_polygons = polygons or []
        self.refresh(keep_view=True)

    def _draw_gds_polygons(self):
        if not self._gds_polygons:
            return
        brush = QBrush(QColor(100, 100, 180, 30))
        pen = QPen(QColor(100, 100, 180, 80), 0)
        for verts in self._gds_polygons:
            if len(verts) < 3:
                continue
            path = QPainterPath()
            path.moveTo(float(verts[0, 0]), float(verts[0, 1]))
            for v in verts[1:]:
                path.lineTo(float(v[0]), float(v[1]))
            path.closeSubpath()
            item = self._scene.addPath(path, pen, brush)
            item.setData(1, "gds_poly")
            self._gds_items.append(item)

    def _pick_nearest_polygon_center(self, x: float, y: float) -> tuple[float, float] | None:
        best_dist = self._pick_threshold_mm
        best_center = None
        for verts in self._gds_polygons:
            cx = float(verts[:, 0].mean())
            cy = float(verts[:, 1].mean())
            d = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_center = (cx, cy)
        return best_center

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._zoom_origin is not None:
            self._cancel_zoom_drag()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Shift and not self._shift_held:
            self._shift_held = True
            self._apply_pick_mode()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Shift:
            self._shift_held = False
            self._apply_pick_mode()
        super().keyReleaseEvent(event)

    def _apply_pick_mode(self):
        active = self._shift_held or self._assignment_mode
        self._pick_mode = self._shift_held
        zooming = self._navigation_mode == "zoom_area"
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag
            if active or zooming
            else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.viewport().setCursor(
            Qt.CursorShape.CrossCursor
            if active or zooming
            else Qt.CursorShape.OpenHandCursor
        )

    def contextMenuEvent(self, event):
        pos = self.mapToScene(event.pos())
        mx, my = pos.x(), pos.y()

        # Check if click is on a mark
        mid = self._find_mark_at(mx, my)
        if mid is not None:
            menu = QMenu(self)
            act_del = QAction("Delete Mark", self)
            act_del.triggered.connect(lambda: self.mark_delete_requested.emit(mid))
            menu.addAction(act_del)
            menu.exec(event.globalPos())
            return

        # Check if click is near a GDS polygon
        if self._gds_polygons:
            center = self._pick_nearest_polygon_center(mx, my)
            if center is not None:
                menu = QMenu(self)
                act_add = QAction("Add Local Mark", self)
                act_add.triggered.connect(lambda: self.mark_add_requested.emit(center[0], center[1]))
                menu.addAction(act_add)
                menu.exec(event.globalPos())
                return

        super().contextMenuEvent(event)

    def mousePressEvent(self, event):
        self.setFocus()
        if (
            self._navigation_mode == "zoom_area"
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._zoom_origin = event.position().toPoint()
            if self._rubber_band is None:
                self._rubber_band = QRubberBand(
                    QRubberBand.Shape.Rectangle, self.viewport()
                )
            self._rubber_band.setGeometry(QRect(self._zoom_origin, self._zoom_origin))
            self._rubber_band.show()
            event.accept()
            return
        if self._shift_held and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            center = self._pick_nearest_polygon_center(pos.x(), pos.y())
            if center:
                cx, cy = center
                mark_id = self._next_mark_id(self._marks)
                self.mark_picked.emit(mark_id, cx, cy)
            return
        if self._assignment_mode and event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            mark_id = self._find_mark_at(pos.x(), pos.y())
            if mark_id is not None:
                self._selected_mark = mark_id
                self.mark_clicked.emit(mark_id)
                return

        item = self.itemAt(event.position().toPoint())
        if item:
            data = item.data(0)
            typ = item.data(1)
            if typ == "field" and data:
                self._selected_field = data
                self.field_clicked.emit(data)
            elif typ == "mark" and data:
                self._selected_mark = data
                self.mark_clicked.emit(data)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        self.mouse_moved.emit(pos.x(), pos.y())
        if self._zoom_origin is not None and self._rubber_band is not None:
            rectangle = QRect(
                self._zoom_origin, event.position().toPoint()
            ).normalized()
            self._rubber_band.setGeometry(rectangle)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            self._zoom_origin is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            rectangle = QRect(
                self._zoom_origin, event.position().toPoint()
            ).normalized()
            self._cancel_zoom_drag()
            self._zoom_to_viewport_rect(rectangle)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom_by(factor, under_mouse=True)
        event.accept()
