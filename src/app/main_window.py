import json
import math
import os
import traceback
from pathlib import Path

from PyQt6.QtCore import QSettings, Qt, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app_info import APP_NAME, APP_VERSION
from core.con_parser import ConParser
from core.field_optimizer import FieldOptimizer
from core.gds_reader import GdsReader
from models.con_file import ConFileData
from models.mark import AlignmentMark
from models.project import ModuleInfo, Project
from ui.canvas import ExposureCanvas
from ui.field_table import FieldTableWidget
from ui.file_editor import FileEditor
from ui.mark_dialog import MarkGeneratorDialog
from ui.mark_panel import MarkPanel
from ui.module_tree import DirectoryTreeWidget
from ui.workflow_bar import WorkflowBar


class MainWindow(QMainWindow):
    def __init__(self, log_path: Path | None = None, settings: QSettings | None = None):
        super().__init__()
        self._log_path = Path(log_path) if log_path else None
        self._settings = settings if settings is not None else QSettings()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(1280, 820)

        self._project = Project()
        self._gds_reader = GdsReader()
        self._con_parser = ConParser()
        self._field_optimizer = FieldOptimizer()
        self._current_con: ConFileData | None = None
        # Active catalog of GDS-detected crosses, preserved across CON loads.
        self._detected_marks: list[AlignmentMark] = []
        self._loaded_cons: dict[str, ConFileData] = {}
        self._module_gds_reader: GdsReader | None = None
        self._pending_assign_field: str | None = None
        self._gds_layer_combo: QComboBox | None = None

        self._setup_ui()
        self._setup_menus()
        self._restore_window_state()

    def _restore_window_state(self):
        geometry = self._settings.value("window/geometry")
        state = self._settings.value("window/state")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if state is not None:
            self.restoreState(state)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 8, 10, 6)
        main_layout.setSpacing(8)

        self._workflow = WorkflowBar()
        main_layout.addWidget(self._workflow)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left: project files
        self._dir_tree = DirectoryTreeWidget()
        self._dir_tree.setMinimumWidth(210)
        self._dir_tree.setMaximumWidth(340)
        self._dir_tree.con_clicked.connect(self._on_tree_con_clicked)
        self._dir_tree.gds_clicked.connect(self._on_tree_gds_clicked)
        self._dir_tree.gds_context_menu.connect(self._on_gds_context_menu)
        splitter.addWidget(self._dir_tree)

        # Center: layout view + advanced CON editor
        center_splitter = QSplitter(Qt.Orientation.Vertical)

        view_panel = QFrame()
        view_panel.setObjectName("layoutViewPanel")
        view_layout = QVBoxLayout(view_panel)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(4)

        view_bar = QHBoxLayout()
        view_title = QLabel("Layout View")
        view_title.setStyleSheet("font-weight: 700;")
        view_bar.addWidget(view_title)
        view_bar.addStretch(1)
        view_bar.addWidget(QLabel("GDS overlay:"))
        self._gds_layer_combo = QComboBox()
        self._gds_layer_combo.setMinimumWidth(90)
        self._gds_layer_combo.addItem("None", None)
        self._gds_layer_combo.currentIndexChanged.connect(self._on_gds_layer_changed)
        view_bar.addWidget(self._gds_layer_combo)
        view_layout.addLayout(view_bar)

        navigation_bar = QHBoxLayout()
        navigation_bar.addWidget(QLabel("Navigation:"))
        self._navigation_group = QButtonGroup(self)
        self._navigation_group.setExclusive(True)

        self._pan_button = QPushButton("Pan")
        self._pan_button.setCheckable(True)
        self._pan_button.setChecked(True)
        self._pan_button.setToolTip(
            "Drag the layout or use the scrollbars to move the view."
        )
        self._navigation_group.addButton(self._pan_button)
        navigation_bar.addWidget(self._pan_button)

        self._zoom_area_button = QPushButton("Zoom Area")
        self._zoom_area_button.setCheckable(True)
        self._zoom_area_button.setToolTip(
            "Drag a rectangle around the area that you want to magnify."
        )
        self._navigation_group.addButton(self._zoom_area_button)
        navigation_bar.addWidget(self._zoom_area_button)

        self._zoom_out_button = QPushButton("−")
        self._zoom_out_button.setFixedWidth(34)
        self._zoom_out_button.setToolTip("Zoom out")
        navigation_bar.addWidget(self._zoom_out_button)

        self._zoom_in_button = QPushButton("+")
        self._zoom_in_button.setFixedWidth(34)
        self._zoom_in_button.setToolTip("Zoom in")
        navigation_bar.addWidget(self._zoom_in_button)

        self._fit_view_button = QPushButton("Fit")
        self._fit_view_button.setToolTip(
            "Fit all exposure fields, local marks, and the GDS overlay in the view."
        )
        navigation_bar.addWidget(self._fit_view_button)

        self._zoom_level_label = QLabel("100%")
        self._zoom_level_label.setMinimumWidth(46)
        self._zoom_level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_level_label.setToolTip("Magnification relative to Fit")
        navigation_bar.addWidget(self._zoom_level_label)
        navigation_bar.addStretch(1)
        view_layout.addLayout(navigation_bar)

        legend = QLabel(
            "Blue outline: exposure field   •   Green cross: local mark   •   "
            "Dashed line: current assignment"
        )
        legend.setStyleSheet("color: palette(text); padding-bottom: 2px;")
        view_layout.addWidget(legend)

        self._canvas = ExposureCanvas()
        self._canvas.field_clicked.connect(self._on_field_selected)
        self._canvas.mark_clicked.connect(self._on_mark_selected)
        self._canvas.mouse_moved.connect(self._on_canvas_mouse_moved)
        self._canvas.mark_picked.connect(self._on_mark_picked)
        self._canvas.mark_add_requested.connect(self._on_mark_add_requested)
        self._canvas.mark_delete_requested.connect(self._on_mark_delete_requested)
        self._pan_button.clicked.connect(
            lambda: self._canvas.set_navigation_mode("pan")
        )
        self._zoom_area_button.clicked.connect(
            lambda: self._canvas.set_navigation_mode("zoom_area")
        )
        self._zoom_out_button.clicked.connect(self._canvas.zoom_out)
        self._zoom_in_button.clicked.connect(self._canvas.zoom_in)
        self._fit_view_button.clicked.connect(self._canvas.fit_all)
        self._canvas.zoom_changed.connect(
            lambda percent: self._zoom_level_label.setText(f"{percent}%")
        )
        view_layout.addWidget(self._canvas)
        center_splitter.addWidget(view_panel)

        self._file_editor = FileEditor()
        self._file_editor.content_changed.connect(self._on_editor_content_changed)
        self._file_editor.save_requested.connect(self._on_save_con)
        self._file_editor.open_requested.connect(self._on_tree_con_clicked)
        self._file_editor.state_changed.connect(self._update_workflow_state)
        center_splitter.addWidget(self._file_editor)

        center_splitter.setSizes([590, 180])
        splitter.addWidget(center_splitter)

        # Right: field assignment first, mark catalog second.
        self._right_tabs = QTabWidget()
        self._field_table = FieldTableWidget()
        self._field_table.order_changed.connect(self._on_order_changed)
        self._field_table.field_selected.connect(self._on_field_selected_from_table)
        self._field_table.enabled_changed.connect(self._on_field_enabled_changed)
        self._field_table.mark_assignment_changed.connect(
            self._on_field_mark_changed)
        self._right_tabs.addTab(self._field_table, "Fields and Order")

        self._mark_panel = MarkPanel()
        self._mark_panel.mark_selected.connect(self._on_mark_catalog_selected)
        self._mark_panel.mark_assign_requested.connect(self._on_mark_assign_from_table)
        self._mark_panel.assign_nearest_requested.connect(self._on_auto_assign)
        self._right_tabs.addTab(self._mark_panel, "Mark Catalog")

        splitter.addWidget(self._right_tabs)

        splitter.setSizes([230, 640, 430])

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel("Ready — start by opening a GDS and a CON file.")
        self._status.addWidget(self._status_label)
        self._coord_label = QLabel("")
        self._coord_label.setStyleSheet("color: gray; padding-right: 10px;")
        self._status.addPermanentWidget(self._coord_label)

        self._workflow.open_gds_requested.connect(self._on_open_gds)
        self._workflow.open_con_requested.connect(self._on_load_con)
        self._workflow.detect_marks_requested.connect(self._on_generate_marks)
        self._workflow.assign_marks_requested.connect(self._focus_assignment_panel)
        self._workflow.save_con_requested.connect(self._on_save_con)
        self._update_workflow_state()

    def _setup_menus(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        open_gds_action = QAction("Open GDS...", self)
        open_gds_action.setShortcut(QKeySequence.StandardKey.Open)
        open_gds_action.triggered.connect(self._on_open_gds)
        file_menu.addAction(open_gds_action)

        open_con_action = QAction("Open CON...", self)
        open_con_action.setShortcut("Ctrl+Shift+O")
        open_con_action.triggered.connect(self._on_load_con)
        file_menu.addAction(open_con_action)

        open_folder_action = QAction("Open Working Folder...", self)
        open_folder_action.triggered.connect(self._on_open_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()
        self._save_con_action = QAction("Save CON", self)
        self._save_con_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_con_action.triggered.connect(self._on_save_con)
        file_menu.addAction(self._save_con_action)

        save_workspace_action = QAction("Save Workspace...", self)
        save_workspace_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_workspace_action)

        load_workspace_action = QAction("Load Workspace...", self)
        load_workspace_action.triggered.connect(self._on_load_project)
        file_menu.addAction(load_workspace_action)

        file_menu.addSeparator()
        export_action = QAction("Export Report...", self)
        export_action.triggered.connect(self._on_export_report)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        workflow_menu = menu.addMenu("Workflow")
        self._detect_marks_action = QAction("Detect Local R23 Marks...", self)
        self._detect_marks_action.triggered.connect(self._on_generate_marks)
        workflow_menu.addAction(self._detect_marks_action)

        self._auto_assign_action = QAction("Assign Nearest Mark to Every Field", self)
        self._auto_assign_action.triggered.connect(self._on_auto_assign)
        workflow_menu.addAction(self._auto_assign_action)

        workflow_menu.addSeparator()
        show_fields_action = QAction("Show Fields and Order", self)
        show_fields_action.triggered.connect(self._focus_assignment_panel)
        workflow_menu.addAction(show_fields_action)

        show_marks_action = QAction("Show Mark Catalog", self)
        show_marks_action.triggered.connect(self._focus_mark_catalog)
        workflow_menu.addAction(show_marks_action)

        help_menu = menu.addMenu("Help")
        logs_action = QAction("Open Log Folder", self)
        logs_action.triggered.connect(self._on_open_log_folder)
        help_menu.addAction(logs_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
        self._update_workflow_state()

    def _on_open_log_folder(self):
        if self._log_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_path.parent)))

    def _on_about(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME} {APP_VERSION}</b><br><br>"
            "Prepare GDS/CON data, local alignment marks, and exposure-field "
            "order for electron-beam lithography.<br><br>"
            "This application does not control the lithography system. "
            "An operator must verify the final CON file before exposure.",
        )

    def _focus_assignment_panel(self):
        self._right_tabs.setCurrentWidget(self._field_table)
        self._status_label.setText(
            "Select a field, then choose a local mark in the last column "
            "or click a green cross in the layout view."
        )

    def _focus_mark_catalog(self):
        self._right_tabs.setCurrentWidget(self._mark_panel)
        self._status_label.setText(
            "The mark catalog combines original CON marks with crosses detected in GDS."
        )

    def _update_workflow_state(self):
        reader = self._module_gds_reader or self._gds_reader
        gds_path = reader.filepath if reader and reader.lib else ""
        con_path = self._current_con.filepath if self._current_con else ""
        fields = self._current_con.fields if self._current_con else []
        marks = self._current_con.marks if self._current_con else self._detected_marks
        assigned_count = sum(bool(field.mark_id) for field in fields)
        self._workflow.set_state(
            gds_path=gds_path,
            con_path=con_path,
            field_count=len(fields),
            mark_count=len(marks),
            assigned_count=assigned_count,
            modified=self._file_editor.is_modified,
        )
        if hasattr(self, "_detect_marks_action"):
            self._detect_marks_action.setEnabled(bool(gds_path))
            self._auto_assign_action.setEnabled(bool(fields and marks))
            self._save_con_action.setEnabled(bool(con_path))

    def _populate_gds_layer_combo(self, reload=False):
        if self._gds_layer_combo is None:
            return
        reader = self._module_gds_reader or self._gds_reader
        self._gds_layer_combo.blockSignals(True)
        if reload:
            self._gds_layer_combo.clear()
            self._gds_layer_combo.addItem("None", None)
        if reader.lib:
            current = self._gds_layer_combo.currentData()
            if reload or current is None:
                for layer, datatype in reader.get_layer_specs():
                    self._gds_layer_combo.addItem(f"L{layer}/{datatype}", (layer, datatype))
        self._gds_layer_combo.blockSignals(False)

    def _on_gds_layer_changed(self, _index: int):
        if self._gds_layer_combo is None:
            return
        layer_spec = self._gds_layer_combo.currentData()
        reader = self._module_gds_reader or self._gds_reader
        if layer_spec is None or not reader.lib:
            self._canvas.set_gds_layer(None)
            return
        layer, datatype = layer_spec
        layer = int(layer)
        datatype = int(datatype)
        try:
            polygons = reader.get_layer_polygons(layer, datatype)
            self._canvas.set_gds_layer((layer, datatype), polygons)
            source = "selected GDS" if self._module_gds_reader else "main GDS"
            self._status_label.setText(
                f"GDS overlay L{layer}/{datatype} ({source}): {len(polygons)} polygons. "
                "Shift-click or right-click a polygon to add a mark."
            )
        except Exception as error:
            self._status_label.setText(f"Could not load the GDS overlay: {error}")

    def _load_current_con(self):
        try:
            if self._current_con:
                self._sync_display(update_editor=False)
                self._status_label.setText(
                    f"CON ready: {len(self._current_con.fields)} fields, "
                    f"{len(self._current_con.marks)} local marks."
                )
            else:
                self._canvas.set_fields([])
                self._canvas.set_marks(self._detected_marks)
                self._canvas.refresh()
                self._field_table.set_fields([])
                self._mark_panel.set_marks(self._detected_marks)
                self._mark_panel.set_fields([])
                self._status_label.setText(
                    "No CON loaded — open a CON file to assign marks to fields."
                )
            self._update_workflow_state()
        except Exception as error:
            self._status_label.setText(f"Could not update the job view: {error}")

    def _on_open_gds(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open GDS File",
            "",
            "GDS Files (*.gds *.GDS);;All Files (*)",
        )
        if not path:
            return
        if self._gds_reader.load(path):
            self._module_gds_reader = None
            self._project.gds_file = path
            self._project.version_name = self._gds_reader.version
            self.setWindowTitle(f"{APP_NAME} — {Path(path).name}")
            self._dir_tree.set_root(str(Path(path).parent))
            self._populate_gds_layer_combo(reload=True)
            self._status_label.setText(
                f"GDS loaded: {Path(path).name} — "
                f"{len(self._gds_reader.get_layer_list())} layers, "
                f"{len(self._gds_reader.get_top_level_modules())} top-level cells."
            )
            self._update_workflow_state()
        else:
            QMessageBox.critical(
                self,
                "Open GDS Failed",
                "The selected GDS file could not be loaded.",
            )

    def _on_open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Working Folder")
        if path:
            self._project.output_dir = path
            self._dir_tree.set_root(path)

    @staticmethod
    def _merge_detected_marks(
        existing_marks: list[AlignmentMark],
        centers: list[tuple[float, float]],
        params: dict,
        tolerance_mm: float = 0.001,
    ) -> tuple[list[AlignmentMark], set[str], int]:
        """Merge GDS centers without changing existing CON mark IDs or coordinates."""
        marks = list(existing_marks)
        target_type = params["mark_type"]
        existing_count = len(marks)
        used_ids = {mark.mark_id for mark in marks}
        matched_existing_ids: set[str] = set()
        prefix = f"GDS_{target_type}" if marks else target_type
        next_index = 1
        added = 0

        for x, y in centers:
            nearest_index = None
            nearest_distance = float("inf")
            for index, mark in enumerate(marks):
                if mark.mark_type != target_type:
                    continue
                distance = math.hypot(x - mark.center_x, y - mark.center_y)
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_index = index
            if nearest_index is not None and nearest_distance <= tolerance_mm:
                if nearest_index < existing_count:
                    matched_existing_ids.add(marks[nearest_index].mark_id)
                continue

            while f"{prefix}_{next_index}" in used_ids:
                next_index += 1
            mark_id = f"{prefix}_{next_index}"
            next_index += 1
            used_ids.add(mark_id)
            marks.append(AlignmentMark(
                mark_id=mark_id,
                mark_type=target_type,
                center_x=x,
                center_y=y,
                arm_length=params["arm_length"],
                arm_width=params["arm_width"],
                layer_group="gate",
            ))
            added += 1

        return marks, matched_existing_ids, added

    def _merge_detected_catalog_into_con(self, con: ConFileData) -> int:
        """Make previously detected GDS crosses available after loading a CON."""
        local_marks = [mark for mark in self._detected_marks if mark.mark_type == "R23"]
        if not local_marks:
            return 0
        template = local_marks[0]
        params = {
            "mark_type": "R23",
            "arm_length": template.arm_length,
            "arm_width": template.arm_width,
        }
        merged, _matched_ids, added = self._merge_detected_marks(
            con.marks,
            [(mark.center_x, mark.center_y) for mark in local_marks],
            params,
        )
        con.marks = merged
        return added

    @staticmethod
    def _layer_spec_label(layer: int, datatype: int | None) -> str:
        return f"{layer}/{datatype}" if datatype is not None else str(layer)

    def _apply_detected_marks(self, reader: GdsReader, params: dict) -> bool:
        layer = params.get("layer")
        datatype = params.get("datatype")
        if layer is None:
            QMessageBox.warning(
                self,
                "No Mark Layer",
                "Select the GDS layer/datatype that contains the local marks.",
            )
            return False
        layer_label = self._layer_spec_label(layer, datatype)
        try:
            centers = reader.extract_polygon_centers(layer, datatype=datatype)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Mark Detection Failed",
                f"Could not detect local marks:\n{error}\n\n{traceback.format_exc()}",
            )
            return False
        if not centers:
            QMessageBox.warning(
                self,
                "No Marks Found",
                f"No crosses or compatible mark geometry were found on layer "
                f"{layer_label}.",
            )
            return False

        detected_marks, _detected_matches, _detected_added = self._merge_detected_marks(
            [],
            centers,
            params,
        )
        self._detected_marks = detected_marks
        existing = list(self._current_con.marks) if self._current_con else []
        marks, matched_ids, added = self._merge_detected_marks(existing, centers, params)
        existing_by_id = {mark.mark_id: mark for mark in existing}
        referenced_ids = set()
        if self._current_con:
            for field in self._current_con.fields:
                mark = existing_by_id.get(field.mark_id)
                if mark is not None and mark.mark_type == params["mark_type"]:
                    referenced_ids.add(field.mark_id)
        unmatched = [
            mark for mark in existing
            if mark.mark_id in referenced_ids and mark.mark_id not in matched_ids
        ]

        try:
            if self._current_con:
                self._current_con.marks = marks
                self._sync_display(update_editor=False)
                self._right_tabs.setCurrentWidget(self._field_table)
            else:
                self._canvas.set_fields([])
                self._canvas.set_marks(self._detected_marks)
                self._canvas.refresh()
                self._mark_panel.set_marks(self._detected_marks)
                self._mark_panel.set_fields([])
                self._field_table.set_fields([])
                self._right_tabs.setCurrentWidget(self._mark_panel)
            self._update_workflow_state()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Display Failed",
                f"Could not display the detected marks:\n"
                f"{error}\n\n{traceback.format_exc()}",
            )
            return False

        message = f"Detected {len(centers)} marks on layer {layer_label}."
        if self._current_con:
            matched_referenced = len(referenced_ids & matched_ids)
            message += (
                f"\nMatched referenced CON R23 marks: "
                f"{matched_referenced}/{len(referenced_ids)}."
                f"\nNew GDS positions added to the catalog: {added}."
            )
        if unmatched:
            details = []
            for mark in unmatched[:5]:
                nearest = min(
                    math.hypot(mark.center_x - x, mark.center_y - y)
                    for x, y in centers
                )
                details.append(
                    f"{mark.mark_id} ({mark.center_x:.4f}, {mark.center_y:.4f}), "
                    f"nearest cross {nearest * 1000:.1f} µm away"
                )
            message += (
                "\n\nThe following CON assignments did not match a detected cross "
                "and were preserved unchanged:\n"
                + "\n".join(details)
            )
            QMessageBox.warning(self, "Marks Detected with Warnings", message)
        else:
            QMessageBox.information(self, "Marks Detected", message)
        return True

    def _on_generate_marks(self):
        if not self._gds_reader.lib:
            QMessageBox.warning(
                self,
                "No GDS Loaded",
                "Open a GDS file before detecting local marks.",
            )
            return
        dialog = MarkGeneratorDialog(self._gds_reader, self)
        if dialog.exec():
            self._apply_detected_marks(dialog._gds_reader, dialog.get_params())

    def _on_load_con(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CON File", "", "CON Files (*.CON);;All Files (*)"
        )
        if not path:
            return
        self._on_tree_con_clicked(path)

    def _on_save_con(self):
        if self._file_editor.save():
            filepath = self._file_editor.current_filepath
            if filepath:
                if self._current_con:
                    self._current_con.filepath = filepath
                    self._current_con.raw_lines = (
                        self._file_editor.plain_text.splitlines(keepends=True)
                    )
                    self._loaded_cons[filepath] = self._current_con
                self._status_label.setText(f"CON saved: {Path(filepath).name}")
                self._update_workflow_state()

    def _on_export_report(self):
        if not self._current_con:
            QMessageBox.warning(self, "No Data", "No data to export")
            return
        from utils.export import generate_report
        report = generate_report(
            self._project.version_name,
            self._project.modules,
            self._project.gate_layers,
            self._project.cap_layers,
            self._project.con_files.gate,
            self._project.con_files.cap,
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "", "Text Files (*.txt);;All Files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(report)
            QMessageBox.information(self, "Exported", f"Report saved to {path}")

    def _on_save_project(self):
        if not self._project.version_name:
            QMessageBox.warning(self, "No Workspace", "There is no workspace to save.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Workspace",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            data = {
                "version": "1.0",
                "gds_file": self._project.gds_file,
                "version_name": self._project.version_name,
                "output_dir": self._project.output_dir,
                "selected_layers": {
                    "gate": self._project.gate_layers,
                    "cap": self._project.cap_layers,
                },
                "modules": [module.to_dict() for module in self._project.modules],
            }
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Workspace Saved", "Workspace saved.")
        except Exception as error:
            QMessageBox.critical(
                self,
                "Save Workspace Failed",
                f"Could not save the workspace:\n{error}",
            )

    def _on_load_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Workspace",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Load Workspace Failed",
                f"Could not load the workspace:\n{error}",
            )
            return
        self._project = Project()
        self._project.gds_file = data.get("gds_file", "")
        self._project.version_name = data.get("version_name", "")
        self._project.output_dir = data.get("output_dir", "")
        selected_layers = data.get("selected_layers", {})
        self._project.gate_layers = selected_layers.get("gate", [])
        self._project.cap_layers = selected_layers.get("cap", [])
        self._project.modules = [
            ModuleInfo.from_dict(module) for module in data.get("modules", [])
        ]

        if self._project.gds_file and os.path.exists(self._project.gds_file):
            self._gds_reader.load(self._project.gds_file)
            self._module_gds_reader = None
            self._populate_gds_layer_combo(reload=True)

        self.setWindowTitle(
            f"{APP_NAME} — workspace {self._project.version_name or 'untitled'}"
        )
        self._status_label.setText(f"Workspace loaded: {Path(path).name}")
        if self._project.output_dir:
            self._dir_tree.set_root(self._project.output_dir)
        self._update_workflow_state()
        QMessageBox.information(self, "Workspace Loaded", "Workspace loaded.")

    def _on_tree_con_clicked(self, path: str):
        """Load from disk only after resolving unsaved editor changes."""
        if not self._file_editor.confirm_discard_changes():
            return
        try:
            con_data = self._con_parser.parse(path)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Open CON Failed",
                f"Could not open the CON file:\n{error}",
            )
            return
        if not self._file_editor.load_file(path):
            return

        added_from_gds = self._merge_detected_catalog_into_con(con_data)
        self._current_con = con_data
        self._loaded_cons[path] = con_data
        self._pending_assign_field = None
        self._mark_panel.set_target_field(None)
        self._canvas.set_assignment_mode(False)
        self._dir_tree.set_root(str(Path(path).parent))
        self._load_current_con()
        status = (
            f"CON loaded: {Path(path).name} — "
            f"{len(con_data.fields)} fields, {len(con_data.marks)} local marks"
        )
        if self._detected_marks:
            status += (
                f" (detected in GDS: {len(self._detected_marks)}, "
                f"added to catalog: {added_from_gds})"
            )
        self._status_label.setText(status)
        self._right_tabs.setCurrentWidget(self._field_table)
        self._update_workflow_state()

    def _on_tree_gds_clicked(self, path: str):
        """Open a GDS file selected in the project-files panel."""
        reader = GdsReader()
        if reader.load(path):
            self._gds_reader = reader
            self._module_gds_reader = None
            self._project.gds_file = path
            self._project.version_name = reader.version
            self.setWindowTitle(f"{APP_NAME} — {Path(path).name}")
            self._populate_gds_layer_combo(reload=True)
            self._status_label.setText(
                f"GDS loaded: {Path(path).name}. Select an overlay layer "
                "or run step 3 to detect R23 marks."
            )
            self._update_workflow_state()
        else:
            self._status_label.setText(f"Could not load GDS: {Path(path).name}")

    def _on_gds_context_menu(self, path: str):
        """Detect marks in a GDS selected from the project-files context menu."""
        reader = GdsReader()
        if not reader.load(path):
            QMessageBox.critical(
                self,
                "Open GDS Failed",
                "The selected GDS file could not be loaded.",
            )
            return
        dialog = MarkGeneratorDialog(reader, self)
        if not dialog.exec():
            return
        params = dialog.get_params()
        reader = dialog._gds_reader
        self._module_gds_reader = reader
        self._populate_gds_layer_combo(reload=True)
        if self._gds_layer_combo is not None:
            layer_spec = (params["layer"], params.get("datatype", 0))
            layer_index = next(
                (index for index in range(self._gds_layer_combo.count())
                 if self._gds_layer_combo.itemData(index) == layer_spec),
                -1,
            )
            if layer_index >= 0:
                self._gds_layer_combo.setCurrentIndex(layer_index)
        self._update_workflow_state()
        self._apply_detected_marks(reader, params)

    def _on_field_selected(self, name: str):
        """Select a field on the canvas and arm mark assignment."""
        if not self._current_con:
            return
        self._pending_assign_field = name
        self._mark_panel.set_target_field(name)
        self._canvas.set_assignment_mode(True)
        self._canvas.set_selected_field(name)
        self._canvas.refresh(keep_view=True)
        self._field_table.select_field(name)
        self._status_label.setText(
            f"Target field: {name}. Click a green mark in the layout view, "
            "or choose a mark in the last table column."
        )

    def _on_field_selected_from_table(self, name: str):
        """Select a table field and arm the next canvas-mark click."""
        if not self._current_con:
            return
        self._pending_assign_field = name
        self._mark_panel.set_target_field(name)
        self._canvas.set_assignment_mode(True)
        self._canvas.set_selected_field(name)
        self._canvas.refresh(keep_view=True)
        self._status_label.setText(
            f"Target field: {name}. Choose a Local Mark in the table, "
            "click a green cross, or use the Mark Catalog."
        )

    def _on_field_mark_changed(self, field_name: str, mark_id: str | None):
        """Reflect a direct Local Mark drop-down change."""
        self._pending_assign_field = None
        self._mark_panel.set_target_field(None)
        self._canvas.set_assignment_mode(False)
        self._canvas.set_selected_field(field_name)
        self._canvas.set_selected_mark(mark_id)
        if mark_id:
            self._mark_panel.select_mark(mark_id)
        self._canvas.refresh(keep_view=True)
        target = mark_id or "no local mark"
        self._status_label.setText(f"Field {field_name} now uses {target}.")
        self._update_workflow_state()

    def _on_mark_catalog_selected(self, mark_id: str):
        """Highlight a catalog mark without changing any field assignment."""
        self._canvas.set_selected_mark(mark_id)
        self._canvas.refresh(keep_view=True)
        if self._pending_assign_field:
            self._status_label.setText(
                f"Mark {mark_id} selected for target field "
                f"{self._pending_assign_field}. Click Assign to Selected Field."
            )
        else:
            self._status_label.setText(
                f"Mark {mark_id} selected. Select a field before assigning it."
            )

    def _on_mark_selected(self, mark_id: str):
        """Assign a canvas-clicked mark to the pending field, or highlight it."""
        self._canvas.set_selected_mark(mark_id)
        self._mark_panel.select_mark(mark_id)
        if self._pending_assign_field and self._current_con:
            field_name = self._pending_assign_field
            mark = self._current_con.find_mark_by_id(mark_id)
            for field in self._current_con.fields:
                if field.name == field_name:
                    field.mark_id = mark_id
                    field.mark_distance = (
                        math.hypot(
                            field.center_x - mark.center_x,
                            field.center_y - mark.center_y,
                        )
                        if mark else None
                    )
                    break
            self._pending_assign_field = None
            self._mark_panel.set_target_field(None)
            self._canvas.set_assignment_mode(False)
            self._sync_display()
            self._status_label.setText(
                f"Field {field_name} now uses local mark {mark_id}."
            )
        else:
            self._canvas.refresh(keep_view=True)
            self._status_label.setText(f"Mark selected: {mark_id}")

    def _on_mark_assign_from_table(self, mark_id: str):
        """Explicitly assign the selected catalog mark to the target field."""
        if not self._pending_assign_field:
            QMessageBox.warning(
                self,
                "No Target Field",
                "Select a field in Fields and Order or in the layout view first.",
            )
            return
        if self._current_con:
            mark = self._current_con.find_mark_by_id(mark_id)
            for field in self._current_con.fields:
                if field.name == self._pending_assign_field:
                    field.mark_id = mark_id
                    field.mark_distance = (
                        math.hypot(
                            field.center_x - mark.center_x,
                            field.center_y - mark.center_y,
                        )
                        if mark else None
                    )
                    break
            field_name = self._pending_assign_field
            self._pending_assign_field = None
            self._mark_panel.set_target_field(None)
            self._canvas.set_assignment_mode(False)
            self._sync_display()
            self._status_label.setText(
                f"Field {field_name} now uses local mark {mark_id}."
            )

    def _on_auto_assign(self):
        if not self._current_con:
            QMessageBox.warning(
                self,
                "No CON Loaded",
                "Open a CON file before assigning marks.",
            )
            return
        if not self._current_con.marks:
            QMessageBox.warning(
                self,
                "No Local Marks",
                "Detect or load local marks before running automatic assignment.",
            )
            return
        self._field_optimizer.assign_nearest_marks(
            self._current_con.fields, self._current_con.marks
        )
        self._pending_assign_field = None
        self._mark_panel.set_target_field(None)
        self._canvas.set_assignment_mode(False)
        self._sync_display()
        QMessageBox.information(
            self,
            "Nearest Marks Assigned",
            "Each field was assigned its geometrically nearest mark. "
            "Review every assignment before exposure.",
        )

    def _on_canvas_mouse_moved(self, x: float, y: float):
        self._coord_label.setText(f"X: {x:.4f} mm  Y: {y:.4f} mm")

    def _on_field_enabled_changed(self):
        """Hide/show fields on canvas based on checkboxes."""
        enabled = self._field_table.get_enabled_names()
        self._canvas.set_enabled_fields(enabled)
        self._canvas.refresh(keep_view=True)

    def _on_order_changed(self):
        """Sync fields, assignments and CON after table edits or reordering."""
        if not self._current_con:
            return
        self._current_con.fields = self._field_table.get_fields()
        if self._pending_assign_field and not any(
            field.name == self._pending_assign_field for field in self._current_con.fields
        ):
            self._pending_assign_field = None
            self._mark_panel.set_target_field(None)
            self._canvas.set_selected_field(None)
            self._canvas.set_assignment_mode(False)
        self._canvas.set_fields(self._current_con.fields)
        self._canvas.set_enabled_fields(self._field_table.get_enabled_names())
        self._canvas.refresh(keep_view=True)
        self._mark_panel.set_fields(self._current_con.fields)
        self._update_editor_from_con()

    def _on_editor_content_changed(self, text: str):
        """Update the complete CON model without writing temporary files."""
        if not self._current_con:
            return
        try:
            new_con = self._con_parser.parse_text(text, self._current_con.filepath)
            self._current_con = new_con
            self._loaded_cons[new_con.filepath] = new_con
            self._sync_display(update_editor=False)
        except ValueError:
            # A partially typed command is expected while the user is editing.
            pass

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

    def _on_mark_picked(self, mark_id: str, cx: float, cy: float):
        """Shift+click on GDS polygon → create mark."""
        mark = AlignmentMark(
            mark_id=mark_id,
            mark_type="R23",
            center_x=cx,
            center_y=cy,
            layer_group="gate",
        )
        if self._current_con:
            self._current_con.marks.append(mark)
            self._canvas.set_marks(self._current_con.marks)
            self._canvas.refresh(keep_view=True)
            self._mark_panel.set_marks(self._current_con.marks)
            self._update_editor_from_con()
        else:
            self._detected_marks.append(mark)
            self._canvas.set_marks(self._detected_marks)
            self._canvas.refresh(keep_view=True)
            self._mark_panel.set_marks(self._detected_marks)
        self._status_label.setText(
            f"Local mark {mark_id} added at ({cx:.4f}, {cy:.4f}) mm."
        )
        self._update_workflow_state()

    def _on_mark_add_requested(self, cx: float, cy: float):
        """Right-click → Add mark from context menu."""
        existing = self._current_con.marks if self._current_con else self._detected_marks
        mark_id = self._next_mark_id(existing)
        self._on_mark_picked(mark_id, cx, cy)

    def _on_mark_delete_requested(self, mark_id: str):
        """Right-click on mark → remove from list."""
        if self._current_con:
            self._current_con.marks = [m for m in self._current_con.marks
                                        if m.mark_id != mark_id]
            for f in self._current_con.fields:
                if f.mark_id == mark_id:
                    f.mark_id = ""
            self._sync_display()
        else:
            self._detected_marks = [m for m in self._detected_marks if m.mark_id != mark_id]
            self._canvas.set_marks(self._detected_marks)
            self._canvas.refresh(keep_view=True)
            self._mark_panel.set_marks(self._detected_marks)
        self._status_label.setText(f"Local mark {mark_id} deleted.")
        self._update_workflow_state()

    def _sync_display(self, update_editor: bool = True):
        """Sync canvas, field_table, mark_panel, and editor with current_con."""
        if not self._current_con:
            return
        try:
            self._canvas.set_field_size(self._current_con.field_size)
            self._canvas.set_fields(self._current_con.fields)
            self._canvas.set_marks(self._current_con.marks)
            self._field_table.set_marks(self._current_con.marks)
            self._field_table.set_fields(self._current_con.fields)
            self._canvas.set_enabled_fields(self._field_table.get_enabled_names())
            self._canvas.refresh()
            self._mark_panel.set_marks(self._current_con.marks)
            self._mark_panel.set_fields(self._current_con.fields)
            if update_editor:
                self._update_editor_from_con()
            self._update_workflow_state()
        except Exception as e:
            tb = traceback.format_exc()
            QMessageBox.critical(
                self,
                "Display Failed",
                f"Could not update the layout view:\n{e}\n\n{tb}",
            )

    def _update_editor_from_con(self):
        if not self._current_con:
            return
        try:
            text = self._con_parser.serialize(self._current_con)
        except ValueError as error:
            self._file_editor.set_save_error(str(error))
            self._status_label.setText(
                "CON preview is invalid — check its format and mark assignments."
            )
            QMessageBox.warning(self, "Review CON Before Saving", str(error))
            return
        self._file_editor.set_content(text, label=self._current_con.module_name)

    def closeEvent(self, event):
        if not self._file_editor.confirm_discard_changes():
            event.ignore()
            return
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())
        self._settings.sync()
        super().closeEvent(event)
