from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.field import ExposureField
from models.mark import AlignmentMark


class MarkPanel(QWidget):
    mark_selected = pyqtSignal(str)
    mark_assign_requested = pyqtSignal(str)
    assign_nearest_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marks: list[AlignmentMark] = []
        self._fields: list[ExposureField] = []
        self._target_field: str | None = None
        self._selected_mark_id: str | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        title = QLabel("Local Mark Catalog")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(title)

        self._instruction = QLabel(
            "Select a field in “Fields and Order”, then select a mark here."
        )
        self._instruction.setWordWrap(True)
        self._instruction.setStyleSheet("color: palette(text);")
        layout.addWidget(self._instruction)

        actions = QHBoxLayout()
        self._assign_button = QPushButton("Assign to Selected Field")
        self._assign_button.setToolTip(
            "Assign the selected catalog mark to the field shown above."
        )
        self._assign_button.clicked.connect(self._on_assign_clicked)
        actions.addWidget(self._assign_button)

        self._auto_button = QPushButton("Assign Nearest to All")
        self._auto_button.setToolTip(
            "Assign the geometrically nearest local mark to every exposure field. "
            "Review every result before exposure."
        )
        self._auto_button.clicked.connect(self.assign_nearest_requested.emit)
        actions.addWidget(self._auto_button)
        layout.addLayout(actions)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(
            ["Mark ID", "Position X, Y (mm)", "Assigned Fields"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self._table)

        self._update_controls()

    @staticmethod
    def _read_only_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _on_assign_clicked(self):
        if self._target_field and self._selected_mark_id:
            self.mark_assign_requested.emit(self._selected_mark_id)

    def set_target_field(self, field_name: str | None):
        self._target_field = field_name
        if field_name:
            self._instruction.setText(
                f"Target field: {field_name}. Select a mark, then click "
                "“Assign to Selected Field”."
            )
        else:
            self._instruction.setText(
                "Select a field in “Fields and Order”, then select a mark here."
            )
        self._update_controls()

    def set_marks(self, marks: list[AlignmentMark]):
        self._marks = list(marks)
        if self._selected_mark_id not in {mark.mark_id for mark in self._marks}:
            self._selected_mark_id = None
        self._populate()

    def set_fields(self, fields: list[ExposureField]):
        self._fields = list(fields)
        if self._target_field not in {field.name for field in self._fields}:
            self.set_target_field(None)
        self._populate()

    def _attached_field_names(self, mark_id: str) -> list[str]:
        return [
            field.name
            for field in self._fields
            if field.mark_id == mark_id
        ]

    def _populate(self):
        selected_mark_id = self._selected_mark_id
        previous = self._table.blockSignals(True)
        try:
            self._table.setRowCount(len(self._marks))
            selected_row = -1
            for row, mark in enumerate(self._marks):
                self._table.setItem(row, 0, self._read_only_item(mark.mark_id))
                self._table.setItem(
                    row,
                    1,
                    self._read_only_item(
                        f"{mark.center_x:.4f}, {mark.center_y:.4f}"
                    ),
                )
                field_names = self._attached_field_names(mark.mark_id)
                self._table.setItem(
                    row,
                    2,
                    self._read_only_item(", ".join(field_names) if field_names else "—"),
                )
                if mark.mark_id == selected_mark_id:
                    selected_row = row
            if selected_row >= 0:
                self._table.selectRow(selected_row)
        finally:
            self._table.blockSignals(previous)
        self._update_controls()

    def select_mark(self, mark_id: str):
        self._selected_mark_id = mark_id
        previous = self._table.blockSignals(True)
        try:
            self._table.clearSelection()
            for row, mark in enumerate(self._marks):
                if mark.mark_id == mark_id:
                    self._table.selectRow(row)
                    break
        finally:
            self._table.blockSignals(previous)
        self._update_controls()

    def _on_selection(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._selected_mark_id = None
            self._update_controls()
            return
        row = rows[0].row()
        if 0 <= row < len(self._marks):
            self._selected_mark_id = self._marks[row].mark_id
            self._update_controls()
            self.mark_selected.emit(self._selected_mark_id)

    def _update_controls(self):
        self._assign_button.setEnabled(
            bool(self._target_field and self._selected_mark_id)
        )
        self._auto_button.setEnabled(bool(self._fields and self._marks))
