from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.gds_reader import GdsReader


class MarkGeneratorDialog(QDialog):
    def __init__(self, gds_reader: GdsReader, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detect Local R23 Marks")
        self.setMinimumWidth(520)
        self._gds_reader = gds_reader
        self._setup_ui()
        self._populate_layers()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        title = QLabel("Find cross-shaped local alignment marks")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(title)

        explanation = QLabel(
            "Choose the exact GDS layer/datatype that contains the crosses. "
            "Cross geometry is recognized automatically. "
            "Detected positions are added to the mark catalog; the source CON "
            "is not changed until a mark is assigned to a field."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: palette(text);")
        layout.addWidget(explanation)

        form = QFormLayout()
        form.setVerticalSpacing(8)

        gds_row = QHBoxLayout()
        self._gds_path = QLineEdit()
        self._gds_path.setReadOnly(True)
        self._gds_path.setPlaceholderText("No GDS file selected")
        if self._gds_reader.filepath:
            self._gds_path.setText(self._gds_reader.filepath)
        gds_row.addWidget(self._gds_path, 1)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._on_browse_gds)
        gds_row.addWidget(browse_button)
        form.addRow("GDS source:", gds_row)

        self._layer_combo = QComboBox()
        self._layer_combo.setMinimumContentsLength(24)
        form.addRow("Mark layer / datatype:", self._layer_combo)

        command_label = QLabel("R23 — local alignment mark")
        command_label.setToolTip(
            "This version writes the supported local-mark command R23."
        )
        form.addRow("CON output command:", command_label)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        detect_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        detect_button.setText("Detect Marks")
        detect_button.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_layers(self):
        self._layer_combo.clear()
        if self._gds_reader.lib:
            for layer, datatype in self._gds_reader.get_layer_specs():
                self._layer_combo.addItem(
                    f"Layer {layer} / datatype {datatype}",
                    (layer, datatype),
                )
        if self._layer_combo.count() == 0:
            self._layer_combo.addItem("No layers available", None)

    def _on_browse_gds(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select GDS File",
            "",
            "GDS Files (*.gds *.GDS);;All Files (*)",
        )
        if path:
            reader = GdsReader()
            if reader.load(path):
                self._gds_reader = reader
                self._gds_path.setText(path)
                self._populate_layers()
            else:
                QMessageBox.critical(
                    self,
                    "Open GDS Failed",
                    "The selected GDS file could not be loaded.",
                )

    def get_params(self) -> dict:
        layer_spec = self._layer_combo.currentData()
        if isinstance(layer_spec, (tuple, list)) and len(layer_spec) == 2:
            layer, datatype = int(layer_spec[0]), int(layer_spec[1])
        else:
            layer, datatype = layer_spec, None
        return {
            "mark_type": "R23",
            "arm_length": 20.0,
            "arm_width": 3.0,
            "layer": layer,
            "datatype": datatype,
        }
