from __future__ import annotations

import os
import sys
from pathlib import Path

import gdspy
import pytest

from core.con_parser import ConParser
from core.gds_reader import GdsReader
from models.con_file import ConFileData
from models.field import ExposureField
from models.mark import AlignmentMark


def test_reused_mark_after_another_mark_roundtrips(tmp_path: Path):
    parser = ConParser()
    con = ConFileData(
        module_name="synthetic",
        marks=[AlignmentMark("A", center_x=1.0), AlignmentMark("B", center_x=2.0)],
        fields=[
            ExposureField("F1", mark_id="A"),
            ExposureField("F2", mark_id="B"),
            ExposureField("F3", mark_id="A"),
        ],
    )
    path = tmp_path / "reuse.CON"
    path.write_text(parser.serialize(con), encoding="utf-8")
    result = parser.parse(path)
    xs = [result.find_mark_by_id(field.mark_id).center_x for field in result.fields]
    assert xs == [1.0, 2.0, 1.0]


def test_non_micron_gds_units_are_normalized(tmp_path: Path):
    library = gdspy.GdsLibrary(unit=1e-9, precision=1e-10)
    cell = library.new_cell("nanometer_units")
    cell.add(gdspy.Rectangle((1000000, 2000000), (1002000, 2002000), layer=82))
    path = tmp_path / "nanometer.gds"
    library.write_gds(str(path))
    reader = GdsReader()
    assert reader.load(path)
    polygons = reader.get_layer_polygons(82)
    assert polygons[0].mean(axis=0) == pytest.approx([1.001, 2.001])
    layer_info = reader.get_layer_info()
    assert list(layer_info) == [82]
    assert layer_info[82].has_data
    assert layer_info[82].polygon_area == pytest.approx(4e-6)


def test_cross_marks_larger_than_old_limit_respect_datatype(tmp_path: Path):
    library = gdspy.GdsLibrary()
    cell = library.new_cell("cross_marks")
    relative_vertices = [
        (-1.5, -8.5),
        (-1.5, -1.5),
        (-8.5, -1.5),
        (-8.5, 1.5),
        (-1.5, 1.5),
        (-1.5, 8.5),
        (1.5, 8.5),
        (1.5, 1.5),
        (8.5, 1.5),
        (8.5, -1.5),
        (1.5, -1.5),
        (1.5, -8.5),
    ]

    def shifted(center_x, center_y):
        return [
            (center_x + offset_x, center_y + offset_y)
            for offset_x, offset_y in relative_vertices
        ]

    cell.add(gdspy.Polygon(shifted(1000, 2000), layer=500, datatype=0))
    cell.add(gdspy.Polygon(shifted(3000, 4000), layer=500, datatype=7))
    path = tmp_path / "crosses.gds"
    library.write_gds(str(path))

    reader = GdsReader()
    assert reader.load(path)
    assert (500, 0) in reader.get_layer_specs()
    assert (500, 7) in reader.get_layer_specs()
    assert reader.extract_polygon_centers(500, datatype=0) == pytest.approx([(1.0, 2.0)])
    assert reader.extract_polygon_centers(500, datatype=7) == pytest.approx([(3.0, 4.0)])
    assert len(reader.extract_polygon_centers(500, datatype=1)) == 0


def test_detected_gds_marks_do_not_replace_existing_con_marks():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.main_window import MainWindow

    existing = [
        AlignmentMark("R23_1", center_x=2.080, center_y=0.439),
        AlignmentMark("R23_2", center_x=4.319, center_y=1.959),
    ]
    params = {
        "mark_type": "R23",
        "arm_length": 20.0,
        "arm_width": 3.0,
        "layer": 500,
        "datatype": 0,
    }
    marks, matched_ids, added = MainWindow._merge_detected_marks(
        existing,
        [(2.080, 0.439), (4.339, 1.959)],
        params,
    )

    assert marks[:2] == existing
    assert matched_ids == {"R23_1"}
    assert added == 1
    assert marks[-1].mark_id == "GDS_R23_1"
    assert (marks[-1].center_x, marks[-1].center_y) == pytest.approx((4.339, 1.959))

def test_local_gds_cross_is_not_mistaken_for_global_r2():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.main_window import MainWindow

    global_mark = AlignmentMark(
        "R2_1",
        mark_type="R2",
        center_x=1.0,
        center_y=2.0,
        corner2_x=3.0,
        corner2_y=4.0,
    )
    params = {"mark_type": "R23", "arm_length": 20.0, "arm_width": 3.0}
    marks, matched_ids, added = MainWindow._merge_detected_marks(
        [global_mark], [(1.0, 2.0)], params
    )
    assert matched_ids == set()
    assert added == 1
    assert [mark.mark_type for mark in marks] == ["R2", "R23"]


def test_save_button_and_layer_dialog(monkeypatch, tmp_path: Path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QPushButton

    from models.layer import LayerInfo
    from ui.file_editor import FileEditor
    from ui.layer_dialog import LayerSelectionDialog

    app = QApplication.instance() or QApplication([])
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: errors.append(args))
    editor = FileEditor()
    saves = []
    editor.save_requested.connect(lambda: saves.append(True))
    button = editor.findChild(QPushButton)
    button.click()
    app.processEvents()
    assert not errors, errors
    assert saves == [True]
    dialog = LayerSelectionDialog({82: LayerInfo(number=82, has_data=True)})
    assert dialog._table.rowCount() == 1
    editor.close()
    dialog.close()


@pytest.mark.parametrize(
    "fields, marks, message",
    [
        ([ExposureField("F"), ExposureField("F")], [], "duplicate"),
        ([ExposureField("F", mark_id="missing")], [], "not found"),
        (
            [ExposureField("F1", mark_id="A"), ExposureField("F2")],
            [AlignmentMark("A")],
            "has no mark",
        ),
    ],
)
def test_invalid_assignments_fail_closed(fields, marks, message):
    con = ConFileData(module_name="synthetic", fields=fields, marks=marks)
    with pytest.raises(ValueError, match=message):
        ConParser().serialize(con)


@pytest.mark.parametrize(
    "text",
    [
        "UNKNOWN_COMMAND;\n!END\n",
        "PCF;\n1,2;\nPPF;\n3,4;\n!END\n",
        "R2 0,0; 1,1;\nR23 2,2;\nPCF;\n3,3;\nPPF;\n3,3;\n!END\n",
    ],
)
def test_unsupported_source_is_not_silently_rewritten(text):
    parser = ConParser()
    con = parser.parse_text(text)
    with pytest.raises(ValueError):
        parser.serialize(con)


def test_comments_are_not_executed_and_header_edits_are_parsed():
    text = (
        "/* R23 100,200; */\n"
        "CZ0.750,75000;\n"
        "/* LayoutBEAMER:DOSE_RESOLUTION = 0.002 */\n"
        "PCF;\n1,2;\nPPF;\n1,2;\n!END\n"
    )
    con = ConParser().parse_text(text)
    assert con.field_size == 0.75
    assert con.resolution == 75000
    assert con.dose_resolution == 0.002
    assert con.marks == []


def test_main_window_loading_and_unsaved_changes(monkeypatch, tmp_path: Path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication, QMessageBox

    import app.main_window as window_module

    application = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(window_module, "QSettings", lambda: settings)
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: errors.append(args))
    first = tmp_path / "first.CON"
    first.write_text("CZ0.750,75000;\nPCF;\n1,2;\nPPF;\n1,2;\n!END\n")
    second = tmp_path / "second.CON"
    second.write_text("CZ0.800,80000;\nPCG;\n3,4;\nPPG;\n3,4;\n!END\n")

    window = window_module.MainWindow()
    window._on_tree_con_clicked(str(first))
    assert not window._file_editor.is_modified
    assert window._canvas._field_size == 0.75
    assert window._current_con.fields[0].name == "F"

    window._file_editor.set_content(window._file_editor.plain_text + "\n")
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Cancel)
    window._on_tree_con_clicked(str(second))
    assert window._file_editor.current_filepath == str(first)

    window._file_editor.set_content(window._file_editor.plain_text, modified=False)
    window._file_editor._editor.file_dropped.emit(str(second))
    assert window._current_con.fields[0].name == "G"
    assert window._canvas._field_size == 0.8
    assert not errors, errors

    window._current_con.raw_lines.append("UNKNOWN_COMMAND;\n")
    window._update_editor_from_con()
    assert not window._file_editor.save()
    assert "UNKNOWN_COMMAND" not in second.read_text()

    window._file_editor.set_content(window._file_editor.plain_text, modified=False)
    window.close()
    application.processEvents()


def test_nested_gds_marks_use_all_parent_transforms_and_ignore_unused_cells(tmp_path):
    library = gdspy.GdsLibrary()
    mark = library.new_cell("nested_alignment_mark")
    mark.add(gdspy.Rectangle((10, 20), (12, 22), layer=82))
    module = library.new_cell("nested_module")
    module.add(gdspy.CellReference(
        mark, origin=(100, 200), rotation=90, magnification=2, x_reflection=True
    ))
    top = library.new_cell("!map_eval_GaN_Vnested")
    top.add(gdspy.CellReference(module, origin=(1000, 2000), rotation=180, magnification=0.5))
    top.add(gdspy.CellReference(module, origin=(-1000, -2000)))
    unused = library.new_cell("unused_alignment_mark")
    unused.add(gdspy.Rectangle((9000, 9000), (9002, 9002), layer=82))
    path = tmp_path / "!map_eval_GaN_Vnested.gds"
    library.write_gds(str(path))

    reader = GdsReader()
    assert reader.load(path)
    centers = sorted(reader.extract_polygon_centers(82))
    assert len(centers) == 2
    assert centers[0] == pytest.approx((-0.858, -1.778))
    assert centers[1] == pytest.approx((0.929, 1.889))


def test_nested_gds_array_expands_every_instance_without_scaling_spacing(tmp_path):
    library = gdspy.GdsLibrary()
    mark = library.new_cell("array_alignment_mark")
    mark.add(gdspy.Rectangle((0, 1), (2, 3), layer=82))
    module = library.new_cell("array_module")
    module.add(gdspy.CellArray(
        mark, 2, 2, (100, 200), origin=(10, 20),
        rotation=90, magnification=2, x_reflection=True,
    ))
    top = library.new_cell("!map_eval_GaN_Varray")
    top.add(gdspy.CellReference(module, origin=(1000, 2000), rotation=180))
    path = tmp_path / "!map_eval_GaN_Varray.gds"
    library.write_gds(str(path))

    reader = GdsReader()
    assert reader.load(path)
    centers = sorted(reader.extract_polygon_centers(82))
    expected = sorted([(0.986, 1.978), (0.786, 1.978), (0.986, 1.878), (0.786, 1.878)])
    assert len(centers) == len(expected)
    for actual, coordinates in zip(centers, expected):
        assert actual == pytest.approx(coordinates)


def test_unused_mark_cell_does_not_suppress_top_cell_fallback(tmp_path):
    library = gdspy.GdsLibrary()
    top = library.new_cell("!map_eval_GaN_Vfallback")
    top.add(gdspy.Rectangle((1000, 2000), (1002, 2002), layer=82))
    unused = library.new_cell("unreachable_mark")
    unused.add(gdspy.Rectangle((9000, 9000), (9002, 9002), layer=82))
    path = tmp_path / "!map_eval_GaN_Vfallback.gds"
    library.write_gds(str(path))

    reader = GdsReader()
    assert reader.load(path)
    centers = reader.extract_polygon_centers(82)
    assert len(centers) == 1
    assert centers[0] == pytest.approx((1.001, 2.001))


def test_gds_reference_cycle_is_rejected_instead_of_returning_local_coordinates():
    library = gdspy.GdsLibrary()
    top = library.new_cell("!map_eval_GaN_Vcycle")
    child = library.new_cell("cycle_child")
    top.add(gdspy.CellReference(child))
    child.add(gdspy.CellReference(top))
    reader = GdsReader()
    reader.lib = library
    reader._version = "cycle"
    with pytest.raises(ValueError, match="Cyclic"):
        reader.extract_polygon_centers(82)


@pytest.fixture
def editable_window(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from app.main_window import MainWindow

    application = QApplication.instance() or QApplication([])
    errors, warnings = [], []
    monkeypatch.setattr(sys, "excepthook", lambda *args: errors.append(args))
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[1:]))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[1:]))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok)
    settings = QSettings(str(tmp_path / "edit-settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(settings=settings)
    window._current_con = ConFileData(
        module_name="table_regression",
        marks=[AlignmentMark("A", center_x=10), AlignmentMark("B", center_x=20)],
        fields=[
            ExposureField("F1", center_x=0, center_y=0, mark_id="A"),
            ExposureField("F2", center_x=1, center_y=1, mark_id="B"),
            ExposureField("F3", center_x=2, center_y=0, mark_id="A"),
        ],
    )
    window._sync_display()
    try:
        yield window, warnings
    finally:
        window._file_editor.set_content(window._file_editor.plain_text, modified=False)
        window.close()
        application.processEvents()
    assert not errors, errors


def test_context_menu_generates_marks_from_the_clicked_gds(editable_window, monkeypatch, tmp_path):
    import app.main_window as window_module

    window, warnings = editable_window
    paths = []
    for name, offset in (("context_first_mark", 0), ("context_second_mark", 1000)):
        library = gdspy.GdsLibrary()
        cell = library.new_cell(name)
        cell.add(gdspy.Rectangle((offset, 0), (offset + 2, 2), layer=82))
        path = tmp_path / f"{name}.gds"
        library.write_gds(str(path))
        paths.append(path)
    assert window._gds_reader.load(paths[0])
    window._current_con = None

    class AcceptedMarkDialog:
        def __init__(self, reader, parent):
            self._gds_reader = reader

        def exec(self):
            return 1

        def get_params(self):
            return {"layer": 82, "mark_type": "R23", "arm_length": 20, "arm_width": 3}

    monkeypatch.setattr(window_module, "MarkGeneratorDialog", AcceptedMarkDialog)
    window._on_gds_context_menu(str(paths[1]))
    assert window._gds_reader.filepath == str(paths[0].resolve())
    assert window._module_gds_reader.filepath == str(paths[1].resolve())
    assert window._gds_layer_combo.currentData() == (82, 0)
    assert len(window._detected_marks) == 1
    assert window._detected_marks[0].center_x == pytest.approx(1.001)
    assert not warnings

def test_only_supported_r23_is_shown_and_legacy_extract_action_is_hidden(
    editable_window,
):
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QComboBox

    from ui.mark_dialog import MarkGeneratorDialog

    window, warnings = editable_window
    action_texts = {
        action.text()
        for action in window.findChildren(QAction)
        if action.text()
    }
    assert "Detect Local R23 Marks..." in action_texts
    assert "Layers+Extract" not in action_texts
    assert not any("extract" in text.casefold() for text in action_texts)

    dialog = MarkGeneratorDialog(GdsReader(), window)
    params = dialog.get_params()
    combo_texts = {
        combo.itemText(index)
        for combo in dialog.findChildren(QComboBox)
        for index in range(combo.count())
    }
    assert params["mark_type"] == "R23"
    assert "R24" not in combo_texts
    assert "R25" not in combo_texts
    dialog.close()
    assert not warnings


def test_gds_marks_remain_available_when_con_is_loaded_after_detection(
    editable_window,
    tmp_path,
):
    from PyQt6.QtWidgets import QApplication, QComboBox

    window, warnings = editable_window
    window._file_editor.set_content(window._file_editor.plain_text, modified=False)
    window._detected_marks = [
        AlignmentMark("R23_1", center_x=1.0, center_y=1.0),
        AlignmentMark("R23_2", center_x=9.0, center_y=9.0),
    ]
    source = (
        "CZ0.600,60000;\n"
        "R23 1.000, 1.000;\n"
        "PCF;\n1.50000,1.50000;\n"
        "PPF;\n1.50000,1.50000;\n"
        "!END\n"
    )
    path = tmp_path / "gds_then_con.CON"
    path.write_text(source, encoding="utf-8")

    window._on_tree_con_clicked(str(path))
    generated_ids = [
        mark.mark_id
        for mark in window._current_con.marks
        if mark.mark_id.startswith("GDS_R23_")
    ]
    assert generated_ids == ["GDS_R23_1"]
    assert len(window._detected_marks) == 2
    combo = window._field_table._table.cellWidget(0, 5)
    assert isinstance(combo, QComboBox)
    assert "added to catalog: 1" in window._status_label.text()
    assert combo.findData(generated_ids[0]) >= 0

    combo.setCurrentIndex(combo.findData(generated_ids[0]))
    QApplication.processEvents()
    assert window._current_con.fields[0].mark_id == generated_ids[0]
    assert "R23 9.000, 9.000;" in window._file_editor.plain_text
    assert path.read_text(encoding="utf-8") == source
    assert not warnings

def test_detection_after_con_adds_choices_without_changing_editor(
    editable_window,
):
    from PyQt6.QtWidgets import QComboBox

    window, warnings = editable_window
    original_text = window._file_editor.plain_text
    window._file_editor.set_content(original_text, modified=False)

    class Reader:
        @staticmethod
        def extract_polygon_centers(layer, datatype=None):
            assert (layer, datatype) == (500, 0)
            return [(10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]

    assert window._apply_detected_marks(
        Reader(),
        {
            "mark_type": "R23",
            "arm_length": 20.0,
            "arm_width": 3.0,
            "layer": 500,
            "datatype": 0,
        },
    )
    generated = [
        mark.mark_id
        for mark in window._current_con.marks
        if mark.mark_id.startswith("GDS_R23_")
    ]
    assert generated == ["GDS_R23_1"]
    combo = window._field_table._table.cellWidget(0, 5)
    assert isinstance(combo, QComboBox)
    assert combo.findData(generated[0]) >= 0
    assert window._file_editor.plain_text == original_text
    assert not window._file_editor.is_modified
    assert not warnings


def test_workflow_is_english_and_starts_with_field_assignment(editable_window):
    from PyQt6.QtWidgets import QPushButton

    window, warnings = editable_window
    button_texts = {
        button.text()
        for button in window._workflow.findChildren(QPushButton)
    }
    assert {
        "1  Open GDS",
        "2  Open CON",
        "3  Detect R23 Marks",
        "4  Assign and Order",
    }.issubset(button_texts)
    assert window._right_tabs.tabText(0) == "Fields and Order"
    assert window._right_tabs.tabText(1) == "Mark Catalog"
    assert window._right_tabs.currentWidget() is window._field_table
    assert not warnings


def test_layout_navigation_has_magnifier_and_visible_scrollbars(editable_window):
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtWidgets import QApplication, QGraphicsView

    window, warnings = editable_window
    canvas = window._canvas

    assert (
        canvas.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    )
    assert canvas.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    assert window._pan_button.text() == "Pan"
    assert window._zoom_area_button.text() == "Zoom Area"
    assert window._fit_view_button.text() == "Fit"

    window._fit_view_button.click()
    QApplication.processEvents()
    initial_scale = canvas.transform().m11()
    window._zoom_in_button.click()
    QApplication.processEvents()
    zoomed_scale = canvas.transform().m11()
    assert zoomed_scale > initial_scale
    assert window._zoom_level_label.text() == "125%"

    window._fit_view_button.click()
    QApplication.processEvents()
    assert canvas.transform().m11() < zoomed_scale
    assert canvas._zoom_ratio() == pytest.approx(1.0)
    assert window._zoom_level_label.text() == "100%"

    window._zoom_area_button.click()
    assert canvas.navigation_mode == "zoom_area"
    assert canvas.dragMode() == QGraphicsView.DragMode.NoDrag

    viewport = canvas.viewport().rect()
    start = QPointF(viewport.width() * 0.25, viewport.height() * 0.25)
    end = QPointF(viewport.width() * 0.75, viewport.height() * 0.75)

    class PointerEvent:
        def __init__(self, position):
            self._position = position
            self.accepted = False

        @staticmethod
        def button():
            return Qt.MouseButton.LeftButton

        def position(self):
            return self._position

        def accept(self):
            self.accepted = True

    press = PointerEvent(start)
    move = PointerEvent(end)
    release = PointerEvent(end)
    canvas.mousePressEvent(press)
    canvas.mouseMoveEvent(move)
    canvas.mouseReleaseEvent(release)
    assert press.accepted and move.accepted and release.accepted
    assert canvas._rubber_band is not None
    assert canvas._zoom_origin is None
    assert canvas._zoom_ratio() > 1.0

    window._pan_button.click()
    assert canvas.navigation_mode == "pan"
    assert canvas.dragMode() == QGraphicsView.DragMode.ScrollHandDrag
    assert not warnings


def test_mark_catalog_selection_requires_explicit_assignment(editable_window):
    from PyQt6.QtWidgets import QApplication

    window, warnings = editable_window
    window._field_table._table.selectRow(0)
    QApplication.processEvents()
    assert window._current_con.fields[0].mark_id == "A"

    window._mark_panel._table.selectRow(1)
    QApplication.processEvents()
    assert window._current_con.fields[0].mark_id == "A"
    assert window._mark_panel._assign_button.isEnabled()

    window._mark_panel._assign_button.click()
    QApplication.processEvents()
    assert window._current_con.fields[0].mark_id == "B"
    assert window._pending_assign_field is None
    assert not warnings


def test_selecting_field_row_then_mark_reassigns_the_field(editable_window):
    from PyQt6.QtWidgets import QApplication

    window, warnings = editable_window
    window._field_table._table.selectRow(0)
    QApplication.processEvents()

    assert window._pending_assign_field == "F1"
    assert window._canvas._assignment_mode
    window._on_mark_selected("B")

    assert window._current_con.fields[0].mark_id == "B"
    assert window._pending_assign_field is None
    assert not window._canvas._assignment_mode
    assert "F1" in window._status_label.text()
    assert "B" in window._status_label.text()
    assert not warnings


def test_assignment_mode_accepts_click_near_mark_cross(editable_window):
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtWidgets import QApplication

    window, warnings = editable_window
    window._field_table._table.selectRow(0)
    QApplication.processEvents()

    mark = window._current_con.find_mark_by_id("B")
    viewport_position = window._canvas.mapFromScene(
        QPointF(mark.center_x + 0.1, mark.center_y + 0.1)
    )

    class MouseEvent:
        @staticmethod
        def button():
            return Qt.MouseButton.LeftButton

        @staticmethod
        def position():
            return QPointF(viewport_position)

    window._canvas.mousePressEvent(MouseEvent())
    QApplication.processEvents()

    assert window._current_con.fields[0].mark_id == "B"
    assert window._pending_assign_field is None
    assert not window._canvas._assignment_mode
    assert not warnings


def test_mark_id_dropdown_reassigns_without_manual_typing(editable_window):
    from PyQt6.QtWidgets import QApplication, QComboBox

    window, warnings = editable_window
    combo = window._field_table._table.cellWidget(0, 5)
    assert isinstance(combo, QComboBox)
    target_index = next(
        index for index in range(combo.count())
        if combo.itemData(index) == "B"
    )
    combo.setCurrentIndex(target_index)
    QApplication.processEvents()

    assert window._current_con.fields[0].mark_id == "B"
    assert window._pending_assign_field is None
    assert not window._canvas._assignment_mode
    parsed = ConParser().parse_text(window._file_editor.plain_text)
    assert parsed.fields[0].mark_id == "R23_1"
    assert parsed.find_mark_by_id("R23_1").center_x == 20
    assert not warnings


def test_field_table_edits_update_the_con_model_and_text(editable_window):
    from PyQt6.QtCore import Qt

    window, warnings = editable_window
    table = window._field_table._table
    assert not table.item(0, 1).flags() & Qt.ItemFlag.ItemIsEditable
    table.item(0, 2).setText("RENAMED")
    table.item(0, 3).setText("1,25")
    table.item(0, 4).setText("-2.5")
    table.item(0, 5).setText("B")
    field = window._current_con.fields[0]
    assert (field.name, field.center_x, field.center_y, field.mark_id) == (
        "RENAMED", 1.25, -2.5, "B"
    )
    result = ConParser().parse_text(window._file_editor.plain_text)
    assert result.fields[0].name == "RENAMED"
    assert result.fields[0].center_x == 1.25
    assert result.fields[0].center_y == -2.5
    assert result.find_mark_by_id(result.fields[0].mark_id).center_x == 20
    assert window._file_editor.is_modified
    assert not warnings


@pytest.mark.parametrize("column, value", [(2, "F2"), (2, "bad name"), (3, "nan"), (4, "inf"), (5, "missing")])
def test_invalid_field_table_edits_are_reverted(editable_window, column, value):
    window, warnings = editable_window
    table = window._field_table._table
    previous_cell = table.item(0, column).text()
    previous_con = window._file_editor.plain_text
    table.item(0, column).setText(value)
    assert table.item(0, column).text() == previous_cell
    assert window._file_editor.plain_text == previous_con
    assert len(warnings) == 1


def test_mark_panel_tracks_reordering_deleting_and_filtering_fields(editable_window):
    from PyQt6.QtCore import Qt

    window, warnings = editable_window
    fields = window._field_table
    panel = window._mark_panel._table
    fields._table.setCurrentCell(2, 0)
    fields._move_up()
    assert panel.item(0, 2).text() == "F1, F3"
    assert panel.item(1, 2).text() == "F2"

    fields._sort_combo.setCurrentText("Raster")
    assert panel.item(0, 2).text() == "F1, F3"
    assert panel.item(1, 2).text() == "F2"

    fields._table.setCurrentCell(1, 0)
    fields._delete_selected()
    assert [field.name for field in window._mark_panel._fields] == ["F2", "F3"]
    assert panel.item(0, 2).text() == "F3"
    assert panel.item(1, 2).text() == "F2"

    fields._table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    fields._keep_checked()
    assert panel.item(0, 2).text() == "F3"
    assert panel.item(1, 2).text() == "—"
    assert [field.index for field in window._current_con.fields] == [0]
    assert not warnings
