from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class WorkflowBar(QFrame):
    """A compact, operator-oriented guide through the EBL preparation flow."""

    open_gds_requested = pyqtSignal()
    open_con_requested = pyqtSignal()
    detect_marks_requested = pyqtSignal()
    assign_marks_requested = pyqtSignal()
    save_con_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workflowBar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(7)

        heading = QHBoxLayout()
        title = QLabel("Exposure Job Workflow")
        title.setObjectName("workflowTitle")
        heading.addWidget(title)
        heading.addSpacing(10)
        subtitle = QLabel(
            "Open the two source files, detect local R23 marks, assign them to fields, "
            "then save a reviewed CON file."
        )
        subtitle.setObjectName("workflowSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle, 1)
        layout.addLayout(heading)

        steps = QHBoxLayout()
        steps.setSpacing(6)
        self._open_gds_button = self._step_button(
            "1  Open GDS",
            "Open the GDSII layout that contains the local alignment marks.",
            self.open_gds_requested,
        )
        self._open_con_button = self._step_button(
            "2  Open CON",
            "Open the source CON file that defines the exposure fields.",
            self.open_con_requested,
        )
        self._detect_button = self._step_button(
            "3  Detect R23 Marks",
            "Find cross-shaped local marks on a selected GDS layer/datatype.",
            self.detect_marks_requested,
        )
        self._assign_button = self._step_button(
            "4  Assign and Order",
            "Review each field-to-mark assignment and the exposure sequence.",
            self.assign_marks_requested,
        )
        self._save_button = self._step_button(
            "5  Save CON",
            "Save the prepared CON file and create a backup of the previous version.",
            self.save_con_requested,
        )
        for button in (
            self._open_gds_button,
            self._open_con_button,
            self._detect_button,
            self._assign_button,
            self._save_button,
        ):
            steps.addWidget(button)
        steps.addStretch(1)
        layout.addLayout(steps)

        state = QHBoxLayout()
        state.setSpacing(12)
        self._gds_state = self._state_label("GDS: not loaded")
        self._con_state = self._state_label("CON: not loaded")
        self._job_state = self._state_label("Fields: 0  |  Local marks: 0")
        state.addWidget(self._gds_state)
        state.addWidget(self._con_state)
        state.addWidget(self._job_state)
        state.addStretch(1)
        layout.addLayout(state)

        self.setStyleSheet(
            "QFrame#workflowBar { border: 1px solid palette(mid); border-radius: 8px; }"
            "QLabel#workflowTitle { font-size: 15px; font-weight: 700; }"
            "QLabel#workflowSubtitle { color: palette(text); }"
            "QLabel[statusChip='true'] { padding: 2px 7px; "
            "background: palette(alternate-base); border-radius: 5px; }"
            "QPushButton[workflowStep='true'] { min-height: 28px; "
            "padding: 3px 10px; font-weight: 600; }"
        )

    @staticmethod
    def _step_button(text: str, tooltip: str, signal) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("workflowStep", True)
        button.setToolTip(tooltip)
        button.clicked.connect(signal.emit)
        return button

    @staticmethod
    def _state_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("statusChip", True)
        return label

    def set_state(
        self,
        *,
        gds_path: str = "",
        con_path: str = "",
        field_count: int = 0,
        mark_count: int = 0,
        assigned_count: int = 0,
        modified: bool = False,
    ):
        gds_name = Path(gds_path).name if gds_path else "not loaded"
        con_name = Path(con_path).name if con_path else "not loaded"
        self._gds_state.setText(f"GDS: {gds_name}")
        self._gds_state.setToolTip(gds_path)
        self._con_state.setText(f"CON: {con_name}")
        self._con_state.setToolTip(con_path)
        self._job_state.setText(
            f"Fields: {field_count}  |  Local marks: {mark_count}  |  "
            f"Assigned: {assigned_count}/{field_count}"
        )

        self._detect_button.setEnabled(bool(gds_path))
        self._assign_button.setEnabled(bool(con_path and mark_count))
        self._save_button.setEnabled(bool(con_path))
        self._save_button.setText("5  Save CON *" if modified else "5  Save CON")
