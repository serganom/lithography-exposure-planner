from __future__ import annotations

from pathlib import Path

import gdspy
import numpy as np
import pytest

from core.con_parser import ConParser
from core.field_optimizer import FieldOptimizer
from core.gds_reader import GdsReader
from models.field import ExposureField
from models.mark import AlignmentMark
from utils.file_io import atomic_write_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_con_parse_serialize_roundtrip(tmp_path: Path):
    source = PROJECT_ROOT / "examples" / "sample.CON"
    parser = ConParser()

    first = parser.parse(source)
    assert [field.name for field in first.fields] == ["FIELD_A", "FIELD_B"]
    assert len(first.marks) == 2
    assert first.fields[0].mark_id == "R23_1"
    assert first.fields[1].mark_id == "R23_2"

    output = tmp_path / "roundtrip.CON"
    output.write_text(parser.serialize(first), encoding="utf-8")
    second = parser.parse(output)

    assert [(field.name, field.center_x, field.center_y) for field in second.fields] == [
        ("FIELD_A", -0.75, 0.5),
        ("FIELD_B", 0.75, 0.5),
    ]
    assert [(mark.center_x, mark.center_y) for mark in second.marks] == [
        (-1.0, 0.5),
        (1.0, 0.5),
    ]


def test_atomic_write_creates_backup(tmp_path: Path):
    target = tmp_path / "job.CON"
    target.write_text("original", encoding="utf-8")

    backup = atomic_write_text(target, "updated", create_backup=True)

    assert target.read_text(encoding="utf-8") == "updated"
    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "original"


def test_field_sorting_and_nearest_mark_assignment():
    fields = [
        ExposureField("D", center_x=1.0, center_y=0.0),
        ExposureField("A", center_x=0.0, center_y=1.0),
        ExposureField("C", center_x=0.0, center_y=0.0),
        ExposureField("B", center_x=1.0, center_y=1.0),
    ]
    ordered = FieldOptimizer.sort_snake(fields)
    assert [field.name for field in ordered] == ["A", "B", "D", "C"]
    assert [field.index for field in ordered] == [0, 1, 2, 3]

    marks = [
        AlignmentMark("LEFT", center_x=-1.0, center_y=0.0),
        AlignmentMark("RIGHT", center_x=2.0, center_y=0.0),
    ]
    FieldOptimizer.assign_nearest_marks(ordered, marks)
    assert ordered[0].mark_id == "LEFT"
    assert ordered[2].mark_id == "RIGHT"


def test_polygon_area_includes_closing_edge():
    reader = GdsReader()
    translated_square = np.array(
        [[5.0, 2.0], [15.0, 2.0], [15.0, 12.0], [5.0, 12.0]]
    )
    assert reader._polygon_area(translated_square) == pytest.approx(100.0)


def test_rotated_reflected_gds_mark_coordinates(tmp_path: Path):
    library = gdspy.GdsLibrary()
    mark_cell = library.new_cell("alignment_mark")
    mark_cell.add(gdspy.Rectangle((100.0, 200.0), (102.0, 202.0), layer=82))
    top = library.new_cell("top")
    top.add(
        gdspy.CellReference(
            mark_cell,
            origin=(1000.0, 2000.0),
            rotation=90.0,
            x_reflection=True,
        )
    )
    gds_path = tmp_path / "rotation_test.gds"
    library.write_gds(str(gds_path))

    reader = GdsReader()
    assert reader.load(gds_path)
    centers = reader.extract_polygon_centers(82)

    assert len(centers) == 1
    assert centers[0][0] == pytest.approx(1.201)
    assert centers[0][1] == pytest.approx(2.101)
