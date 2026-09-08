from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.layer import LayerInfo


class LayerSelectionDialog(QDialog):
    def __init__(self, layers: dict[int, LayerInfo], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Layer Selection")
        self.setMinimumSize(650, 500)
        self._layers = layers
        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        info = QLabel(
            "Select layers for Gate and/or Cap groups.\n"
            "A layer can belong to both Gate and Cap."
        )
        info.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        layout.addWidget(info)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Layer", "Has Data", "Gate", "Cap", "Area (sq.mm)"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QLabel("Gate:"))
        btn_layout.addWidget(self._btn(self, "Select All", self._select_all_gate))
        btn_layout.addWidget(self._btn(self, "Clear All", self._clear_all_gate))
        btn_layout.addStretch()
        btn_layout.addWidget(QLabel("Cap:"))
        btn_layout.addWidget(self._btn(self, "Select All", self._select_all_cap))
        btn_layout.addWidget(self._btn(self, "Clear All", self._clear_all_cap))
        layout.addLayout(btn_layout)

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btm = QHBoxLayout()
        btm.addStretch()
        btm.addWidget(btn_ok)
        btm.addWidget(btn_cancel)
        layout.addLayout(btm)

    def _btn(self, parent, text, slot):
        b = QPushButton(text)
        b.clicked.connect(slot)
        return b

    def _populate(self):
        self._table.setRowCount(len(self._layers))
        for i, (num, info) in enumerate(sorted(self._layers.items())):
            self._table.setItem(i, 0, QTableWidgetItem(str(num)))
            has_data = "Yes" if info.has_data else "No"
            item_data = QTableWidgetItem(has_data)
            if info.has_data:
                item_data.setBackground(QBrush(QColor(200, 255, 200)))
            else:
                item_data.setBackground(QBrush(QColor(255, 220, 220)))
            self._table.setItem(i, 1, item_data)

            cb_gate = QCheckBox()
            cb_gate.setChecked(info.gate_enabled)
            wg_gate = QWidget()
            wl_gate = QHBoxLayout(wg_gate)
            wl_gate.addWidget(cb_gate)
            wl_gate.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setCellWidget(i, 2, wg_gate)

            cb_cap = QCheckBox()
            cb_cap.setChecked(info.cap_enabled)
            wg_cap = QWidget()
            wl_cap = QHBoxLayout(wg_cap)
            wl_cap.addWidget(cb_cap)
            wl_cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setCellWidget(i, 3, wg_cap)

            area_item = QTableWidgetItem(f"{info.polygon_area:.2f}" if info.has_data else "-")
            self._table.setItem(i, 4, area_item)

        self._table.resizeColumnsToContents()

    def _select_all_gate(self):
        self._set_check_col(2, True)

    def _clear_all_gate(self):
        self._set_check_col(2, False)

    def _select_all_cap(self):
        self._set_check_col(3, True)

    def _clear_all_cap(self):
        self._set_check_col(3, False)

    def _set_check_col(self, col: int, val: bool):
        for i in range(self._table.rowCount()):
            w = self._table.cellWidget(i, col)
            if w:
                cb = w.findChild(QCheckBox)
                if cb:
                    cb.setChecked(val)

    def _get_checked(self, col: int) -> list[int]:
        result = []
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            w = self._table.cellWidget(i, col)
            if w:
                cb = w.findChild(QCheckBox)
                if cb and cb.isChecked():
                    result.append(int(item.text()))
        return sorted(result)

    def get_gate_layers(self) -> list[int]:
        return self._get_checked(2)

    def get_cap_layers(self) -> list[int]:
        return self._get_checked(3)
