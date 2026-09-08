import math
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.field import ExposureField
from models.mark import AlignmentMark


class FieldTableWidget(QWidget):
    order_changed = pyqtSignal()
    field_selected = pyqtSignal(str)
    enabled_changed = pyqtSignal()
    mark_assignment_changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields: list[ExposureField] = []
        self._enabled: list[bool] = []
        self._mark_ids: set[str] = set()
        self._marks: list[AlignmentMark] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        title = QLabel("Field Sequence & Local Mark Assignment")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(title)

        hint = QLabel(
            "Select a row to highlight a field. Choose its local mark in the last "
            "column, or click a green cross in the layout view."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(text);")
        layout.addWidget(hint)

        order_controls = QHBoxLayout()
        order_controls.addWidget(QLabel("Order:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(
            ["Manual", "Snake", "Raster", "Radial (center-out)"]
        )
        self._sort_combo.setToolTip(
            "Reorder all fields using a preset path. Assignments stay attached "
            "to their fields."
        )
        self._sort_combo.currentTextChanged.connect(self._on_sort_changed)
        order_controls.addWidget(self._sort_combo)
        order_controls.addStretch(1)

        self._up_button = QPushButton("Move Up")
        self._up_button.clicked.connect(self._move_up)
        order_controls.addWidget(self._up_button)

        self._down_button = QPushButton("Move Down")
        self._down_button.clicked.connect(self._move_down)
        order_controls.addWidget(self._down_button)
        layout.addLayout(order_controls)

        row_controls = QHBoxLayout()
        self._remove_unchecked_button = QPushButton("Remove Unchecked")
        self._remove_unchecked_button.setToolTip(
            "Remove every field whose Use checkbox is cleared."
        )
        self._remove_unchecked_button.clicked.connect(self._keep_checked)
        row_controls.addWidget(self._remove_unchecked_button)

        self._delete_button = QPushButton("Delete Selected")
        self._delete_button.setToolTip("Remove the selected field from the output CON.")
        self._delete_button.clicked.connect(self._delete_selected)
        row_controls.addWidget(self._delete_button)
        row_controls.addStretch(1)
        layout.addLayout(row_controls)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Use", "Order", "Field", "X (mm)", "Y (mm)", "Local Mark"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(2, 150)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(30)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        self._update_controls()

    def set_marks(self, marks: list[AlignmentMark]):
        self._marks = list(marks)
        self._mark_ids = {mark.mark_id for mark in marks}
        if self._fields:
            self._populate()

    @staticmethod
    def _distance_to_mark(field: ExposureField, mark: AlignmentMark) -> float:
        return math.hypot(field.center_x - mark.center_x, field.center_y - mark.center_y)

    def _create_mark_combo(self, row: int, field: ExposureField) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(f"markCombo_{row}")
        combo.setMaxVisibleItems(20)
        combo.setMinimumContentsLength(20)
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        combo.setToolTip(
            "Choose a local mark for this field. Marks are sorted by distance "
            "from the field center."
        )
        combo.addItem("No local mark", None)

        ordered_marks = sorted(
            self._marks,
            key=lambda mark: (self._distance_to_mark(field, mark), mark.mark_id),
        )
        selected_index = 0
        for mark in ordered_marks:
            distance = self._distance_to_mark(field, mark)
            combo.addItem(
                f"{mark.mark_id}  |  X {mark.center_x:.4f}, Y {mark.center_y:.4f}"
                f"  |  distance {distance:.4f} mm",
                mark.mark_id,
            )
            if mark.mark_id == field.mark_id:
                selected_index = combo.count() - 1

        if field.mark_id and field.mark_id not in self._mark_ids:
            combo.addItem(
                f"WARNING: {field.mark_id} — mark not found",
                field.mark_id,
            )
            selected_index = combo.count() - 1

        combo.setCurrentIndex(selected_index)
        combo.currentIndexChanged.connect(
            lambda _index, selected_field=field, control=combo: self._on_mark_combo_changed(
                selected_field, control.currentData()
            )
        )
        return combo

    def _on_mark_combo_changed(
        self, field: ExposureField, mark_id: str | None
    ):
        if field not in self._fields or field.mark_id == mark_id:
            return
        row = self._fields.index(field)
        self._table.selectRow(row)
        field.mark_id = mark_id
        mark = next((item for item in self._marks if item.mark_id == mark_id), None)
        field.mark_distance = self._distance_to_mark(field, mark) if mark else None
        self.mark_assignment_changed.emit(field.name, mark_id)
        self.order_changed.emit()

    def set_fields(self, fields: list[ExposureField]):
        old_enabled = {field.name: enabled for field, enabled in zip(
            self._fields, self._enabled
        )}
        self._fields = list(fields)
        self._enabled = [old_enabled.get(field.name, True) for field in self._fields]
        self._populate()

    def _populate(self):
        selected_name = None
        selected_row = self._table.currentRow()
        if 0 <= selected_row < len(self._fields):
            selected_name = self._fields[selected_row].name

        previous = self._table.blockSignals(True)
        try:
            self._table.setRowCount(len(self._fields))
            row_to_select = -1
            for row, field in enumerate(self._fields):
                field.index = row
                checkbox = QTableWidgetItem()
                checkbox.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                )
                checkbox.setCheckState(
                    Qt.CheckState.Checked if self._enabled[row] else Qt.CheckState.Unchecked
                )
                checkbox.setToolTip("Include this field in the output CON.")
                self._table.setItem(row, 0, checkbox)

                order_item = QTableWidgetItem(str(row + 1))
                order_item.setFlags(order_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, 1, order_item)

                field_item = QTableWidgetItem(field.name)
                field_item.setToolTip("Double-click to edit the field name.")
                self._table.setItem(row, 2, field_item)

                x_item = QTableWidgetItem(f"{field.center_x:.5f}")
                x_item.setToolTip("Double-click to edit the X coordinate in millimetres.")
                self._table.setItem(row, 3, x_item)

                y_item = QTableWidgetItem(f"{field.center_y:.5f}")
                y_item.setToolTip("Double-click to edit the Y coordinate in millimetres.")
                self._table.setItem(row, 4, y_item)

                mark_item = QTableWidgetItem(field.mark_id or "")
                mark_item.setFlags(mark_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, 5, mark_item)
                self._table.setCellWidget(row, 5, self._create_mark_combo(row, field))

                if field.name == selected_name:
                    row_to_select = row
            if row_to_select >= 0:
                self._table.selectRow(row_to_select)
        finally:
            self._table.blockSignals(previous)
        self._update_controls()

    def _on_item_changed(self, item):
        row, column = item.row(), item.column()
        if not 0 <= row < len(self._fields):
            return
        if column == 0:
            self._enabled[row] = item.checkState() == Qt.CheckState.Checked
            self.enabled_changed.emit()
            self._update_controls()
            return
        if column not in (2, 3, 4, 5):
            self._populate()
            return

        field = self._fields[row]
        text = item.text().strip()
        try:
            if column == 2:
                if not re.fullmatch(r"[^\s;]+", text):
                    raise ValueError(
                        "A field name cannot be empty or contain spaces or ';'."
                    )
                if any(other is not field and other.name == text for other in self._fields):
                    raise ValueError(f"A field named {text} already exists.")
                field.name = text
            elif column in (3, 4):
                coordinate = float(text.replace(",", "."))
                if not math.isfinite(coordinate):
                    raise ValueError("A coordinate must be a finite number.")
                if column == 3:
                    field.center_x = coordinate
                else:
                    field.center_y = coordinate
            else:
                if text and text not in self._mark_ids:
                    raise ValueError(
                        f"Mark {text} was not found. Select an existing Mark ID."
                    )
                field.mark_id = text or None
        except ValueError as error:
            self._populate()
            QMessageBox.warning(self, "Invalid Value", str(error))
            return

        field.mark_distance = None
        if column == 5:
            self.mark_assignment_changed.emit(field.name, field.mark_id)
        self._populate()
        self.order_changed.emit()

    def get_enabled_fields(self) -> list[ExposureField]:
        return [
            field for row, field in enumerate(self._fields)
            if self._enabled[row]
        ]

    def get_enabled_names(self) -> set[str]:
        return {
            field.name for row, field in enumerate(self._fields)
            if self._enabled[row]
        }

    def _keep_checked(self):
        self._fields = self.get_enabled_fields()
        self._enabled = [True] * len(self._fields)
        self._populate()
        self.order_changed.emit()

    def _delete_selected(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._fields):
            del self._fields[row]
            del self._enabled[row]
            self._populate()
            self.order_changed.emit()

    def _on_sort_changed(self, method: str):
        if not self._fields or method == "Manual":
            return
        from core.field_optimizer import FieldOptimizer

        enabled_by_identity = {
            id(field): enabled for field, enabled in zip(self._fields, self._enabled)
        }
        optimizer = FieldOptimizer()
        if method == "Snake":
            self._fields = optimizer.sort_snake(self._fields)
        elif method == "Raster":
            self._fields = optimizer.sort_raster(self._fields)
        elif method == "Radial (center-out)":
            self._fields = optimizer.sort_spiral(self._fields)
        self._enabled = [
            enabled_by_identity.get(id(field), True) for field in self._fields
        ]
        self._populate()
        self.order_changed.emit()

    def _move_up(self):
        row = self._table.currentRow()
        if row > 0:
            self._fields[row], self._fields[row - 1] = (
                self._fields[row - 1], self._fields[row]
            )
            self._enabled[row], self._enabled[row - 1] = (
                self._enabled[row - 1], self._enabled[row]
            )
            self._populate()
            self._table.selectRow(row - 1)
            self.order_changed.emit()

    def _move_down(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._fields) - 1:
            self._fields[row], self._fields[row + 1] = (
                self._fields[row + 1], self._fields[row]
            )
            self._enabled[row], self._enabled[row + 1] = (
                self._enabled[row + 1], self._enabled[row]
            )
            self._populate()
            self._table.selectRow(row + 1)
            self.order_changed.emit()

    def _on_selection_changed(self):
        rows = self._table.selectionModel().selectedRows()
        self._update_controls()
        if rows:
            row = rows[0].row()
            if 0 <= row < len(self._fields):
                self.field_selected.emit(self._fields[row].name)

    def _update_controls(self):
        row = self._table.currentRow()
        has_selection = 0 <= row < len(self._fields)
        self._sort_combo.setEnabled(bool(self._fields))
        self._up_button.setEnabled(has_selection and row > 0)
        self._down_button.setEnabled(
            has_selection and row < len(self._fields) - 1
        )
        self._delete_button.setEnabled(has_selection)
        self._remove_unchecked_button.setEnabled(
            any(not enabled for enabled in self._enabled)
        )

    def select_field(self, name: str):
        for row, field in enumerate(self._fields):
            if field.name == name:
                self._table.selectRow(row)
                break

    def get_fields(self) -> list[ExposureField]:
        return self._fields
