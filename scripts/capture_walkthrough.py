"""Create public MP4 and GIF walkthroughs using synthetic EBL job data only."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mp4",
        type=Path,
        default=Path("docs/media/lithography-exposure-planner-demo.mp4"),
    )
    parser.add_argument(
        "--gif",
        type=Path,
        default=Path("docs/media/lithography-exposure-planner-demo.gif"),
    )
    parser.add_argument("--fps", type=int, default=12)
    args = parser.parse_args()

    if args.fps <= 0:
        raise ValueError("FPS must be positive.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to encode the walkthrough.")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import numpy as np
    from PyQt6.QtCore import QPointF, QSettings, Qt
    from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel

    from app.main_window import MainWindow
    from app_info import APP_NAME, APP_VERSION
    from models.con_file import ConFileData
    from models.field import ExposureField
    from models.mark import AlignmentMark

    mp4_path = args.mp4.resolve()
    gif_path = args.gif.resolve()
    mp4_path.parent.mkdir(parents=True, exist_ok=True)
    gif_path.parent.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    with tempfile.TemporaryDirectory(prefix="litho-walkthrough-") as temporary:
        temporary_path = Path(temporary)
        frame_directory = temporary_path / "frames"
        frame_directory.mkdir()
        settings = QSettings(
            str(temporary_path / "preferences.ini"),
            QSettings.Format.IniFormat,
        )
        window = MainWindow(settings=settings)
        window.resize(1440, 900)
        window.setWindowTitle(f"{APP_NAME} {APP_VERSION} — synthetic walkthrough")
        window._dir_tree.set_root(str(PROJECT_ROOT / "examples"))

        positions = [
            (-1.35, -0.90),
            (0.00, -0.90),
            (1.35, -0.90),
            (-1.35, 0.00),
            (0.00, 0.00),
            (1.35, 0.00),
            (-1.35, 0.90),
            (0.00, 0.90),
            (1.35, 0.90),
        ]
        marks = [
            AlignmentMark(
                mark_id=f"R23_{index + 1}",
                center_x=x,
                center_y=y,
                arm_length=20.0,
                arm_width=3.0,
            )
            for index, (x, y) in enumerate(positions)
        ]
        field_by_position = [
            ExposureField(
                name=f"FIELD_{index + 1:02d}",
                center_x=x + 0.18,
                center_y=y + 0.14,
            )
            for index, (x, y) in enumerate(positions)
        ]
        scrambled_order = [8, 0, 5, 2, 6, 1, 7, 3, 4]
        fields = [field_by_position[index] for index in scrambled_order]
        assignment_by_name = {
            field.name: marks[index].mark_id
            for index, field in enumerate(field_by_position)
        }

        synthetic_gds = temporary_path / "synthetic_layout.gds"
        synthetic_con = temporary_path / "synthetic_source.CON"
        con = ConFileData(
            filepath=str(synthetic_con),
            module_name="synthetic_source",
            field_size=0.65,
            fields=fields,
        )
        window._current_con = con
        window._gds_reader.filepath = str(synthetic_gds)
        window._project.gds_file = str(synthetic_gds)
        window._project.version_name = "synthetic"

        def cross_polygon(
            center_x: float,
            center_y: float,
            arm: float = 0.13,
            width: float = 0.035,
        ) -> np.ndarray:
            points = [
                (-width, -arm),
                (width, -arm),
                (width, -width),
                (arm, -width),
                (arm, width),
                (width, width),
                (width, arm),
                (-width, arm),
                (-width, width),
                (-arm, width),
                (-arm, -width),
                (-width, -width),
            ]
            return np.asarray(
                [
                    (center_x + offset_x, center_y + offset_y)
                    for offset_x, offset_y in points
                ],
                dtype=float,
            )

        polygons = [cross_polygon(x, y) for x, y in positions]
        window._gds_layer_combo.blockSignals(True)
        window._gds_layer_combo.addItem("L500/0 (synthetic)", (500, 0))
        window._gds_layer_combo.setCurrentIndex(1)
        window._gds_layer_combo.blockSignals(False)

        window._sync_display()
        initial_text = window._con_parser.serialize(con)
        window._file_editor.set_content(
            initial_text,
            label="synthetic_source.CON",
            modified=False,
        )
        window._canvas.set_gds_layer((500, 0), polygons)
        window._right_tabs.setCurrentWidget(window._field_table)
        window._status_label.setText("SYNTHETIC WALKTHROUGH — not an exposure job")
        window._update_workflow_state()
        window.show()
        app.processEvents()
        window._canvas.fit_all()

        caption = QLabel(window.centralWidget())
        caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        caption.setWordWrap(True)
        caption.setFixedSize(1040, 82)
        caption.setStyleSheet(
            "QLabel {"
            "background-color: rgba(7, 28, 48, 225);"
            "color: white;"
            "border: 1px solid rgba(255, 255, 255, 70);"
            "border-radius: 10px;"
            "padding: 10px 18px;"
            "font-size: 17px;"
            "}"
        )
        caption.move(
            (window.centralWidget().width() - caption.width()) // 2,
            window.centralWidget().height() - caption.height() - 18,
        )
        caption_effect = QGraphicsOpacityEffect(caption)
        caption.setGraphicsEffect(caption_effect)
        caption.raise_()
        caption.show()

        def set_caption(step: str, title: str, detail: str) -> None:
            caption.setText(
                f"<b>{step} · {title}</b><br>"
                f"<span style='font-size: 14px'>{detail}</span>"
            )

        def set_workflow(mark_count: int, assigned_count: int, modified: bool) -> None:
            window._workflow.set_state(
                gds_path=str(synthetic_gds),
                con_path=str(synthetic_con),
                field_count=len(con.fields),
                mark_count=mark_count,
                assigned_count=assigned_count,
                modified=modified,
            )

        frame_index = 0

        def capture_scene(
            duration: float,
            step: str,
            title: str,
            detail: str,
            setup,
            animate=None,
        ) -> None:
            nonlocal frame_index
            setup()
            set_caption(step, title, detail)
            app.processEvents()
            frame_count = max(1, round(duration * args.fps))
            for local_index in range(frame_count):
                progress = (local_index + 1) / frame_count
                if animate is not None:
                    animate(progress)
                fade = min(progress / 0.12, (1.0 - progress) / 0.12, 1.0)
                caption_effect.setOpacity(max(0.05, fade))
                caption.raise_()
                app.processEvents()
                destination = frame_directory / f"frame_{frame_index:05d}.png"
                if not window.grab().save(str(destination)):
                    raise RuntimeError(f"Could not save frame {frame_index}.")
                frame_index += 1

        def setup_sources() -> None:
            con.marks = []
            for field in con.fields:
                field.mark_id = None
                field.mark_distance = None
            window._sync_display(update_editor=False)
            window._file_editor.set_content(
                initial_text,
                label="synthetic_source.CON",
                modified=False,
            )
            window._canvas.set_gds_layer((500, 0), polygons)
            window._right_tabs.setCurrentWidget(window._field_table)
            window._canvas.fit_all()
            set_workflow(mark_count=0, assigned_count=0, modified=False)

        capture_scene(
            2.6,
            "1 / 8",
            "Open GDS and CON",
            "Start with the layout and the source exposure-field job.",
            setup_sources,
        )

        detection_state = {"count": -1}

        def setup_detection() -> None:
            detection_state["count"] = -1
            window._right_tabs.setCurrentWidget(window._mark_panel)
            window._mark_panel.set_fields(con.fields)
            window._mark_panel.set_marks([])
            window._canvas.set_marks([])
            window._canvas.refresh(keep_view=True)

        def animate_detection(progress: float) -> None:
            count = min(len(marks), round(progress * len(marks)))
            if count == detection_state["count"]:
                return
            detection_state["count"] = count
            visible_marks = marks[:count]
            window._canvas.set_marks(visible_marks)
            window._canvas.refresh(keep_view=True)
            window._mark_panel.set_marks(visible_marks)
            window._mark_panel.set_fields(con.fields)
            set_workflow(mark_count=count, assigned_count=0, modified=False)

        capture_scene(
            3.8,
            "2 / 8",
            "Detect local R23 marks",
            "Choose the exact GDS layer/datatype; cross centers enter the catalog.",
            setup_detection,
            animate_detection,
        )

        def setup_catalog() -> None:
            con.marks = list(marks)
            window._sync_display(update_editor=False)
            window._file_editor.set_content(
                initial_text,
                label="synthetic_source.CON",
                modified=False,
            )
            window._right_tabs.setCurrentWidget(window._mark_panel)
            window._mark_panel._table.selectRow(4)
            set_workflow(mark_count=len(marks), assigned_count=0, modified=False)

        capture_scene(
            2.8,
            "3 / 8",
            "Review the Mark Catalog",
            "Selecting a catalog row highlights a mark; it does not change the CON.",
            setup_catalog,
        )

        assignment_state = {"count": 0}

        def setup_assignment() -> None:
            assignment_state["count"] = 0
            for field in con.fields:
                field.mark_id = None
                field.mark_distance = None
            window._pending_assign_field = None
            window._mark_panel.set_target_field(None)
            window._canvas.set_assignment_mode(False)
            window._sync_display(update_editor=False)
            window._right_tabs.setCurrentWidget(window._field_table)
            set_workflow(mark_count=len(marks), assigned_count=0, modified=False)

        def animate_assignment(progress: float) -> None:
            target_count = min(len(con.fields), int(progress * (len(con.fields) + 1)))
            if target_count <= assignment_state["count"]:
                return
            for index in range(assignment_state["count"], target_count):
                field = con.fields[index]
                field.mark_id = assignment_by_name[field.name]
                mark = con.find_mark_by_id(field.mark_id)
                field.mark_distance = (
                    ((field.center_x - mark.center_x) ** 2
                     + (field.center_y - mark.center_y) ** 2) ** 0.5
                    if mark
                    else None
                )
            assignment_state["count"] = target_count
            window._sync_display(update_editor=False)
            if target_count:
                window._field_table.select_field(con.fields[target_count - 1].name)
            set_workflow(
                mark_count=len(marks),
                assigned_count=target_count,
                modified=target_count > 0,
            )
            if target_count == len(con.fields):
                window._pending_assign_field = None
                window._mark_panel.set_target_field(None)
                window._canvas.set_assignment_mode(False)
                window._update_editor_from_con()

        capture_scene(
            4.8,
            "4 / 8",
            "Assign a local mark to each field",
            "Use the field list, an explicit catalog action, or click a green mark.",
            setup_assignment,
            animate_assignment,
        )

        replacement_state = {"changed": False}
        replacement_field_name = "FIELD_01"
        original_mark_id = "R23_1"
        replacement_mark_id = "R23_2"

        def setup_replacement() -> None:
            replacement_state["changed"] = False
            window._right_tabs.setCurrentWidget(window._field_table)
            window._canvas.fit_all()
            target_field = next(
                field
                for field in con.fields
                if field.name == replacement_field_name
            )
            target_field.mark_id = original_mark_id
            original_mark = con.find_mark_by_id(original_mark_id)
            target_field.mark_distance = (
                ((target_field.center_x - original_mark.center_x) ** 2
                 + (target_field.center_y - original_mark.center_y) ** 2) ** 0.5
                if original_mark
                else None
            )
            window._sync_display(update_editor=False)
            window._field_table._table.clearSelection()
            window._field_table.select_field(replacement_field_name)
            window._canvas.set_selected_mark(original_mark_id)
            window._canvas.refresh(keep_view=True)
            window._status_label.setText(
                f"{replacement_field_name} currently uses {original_mark_id}."
            )
            set_workflow(
                mark_count=len(marks),
                assigned_count=len(con.fields),
                modified=True,
            )

        def animate_replacement(progress: float) -> None:
            if progress < 0.46 or replacement_state["changed"]:
                return
            replacement_state["changed"] = True
            row = next(
                index
                for index, field in enumerate(window._field_table.get_fields())
                if field.name == replacement_field_name
            )
            combo = window._field_table._table.cellWidget(row, 5)
            replacement_index = combo.findData(replacement_mark_id)
            if replacement_index < 0:
                raise RuntimeError(
                    f"Walkthrough mark {replacement_mark_id} is unavailable."
                )
            combo.setCurrentIndex(replacement_index)
            window._field_table.select_field(replacement_field_name)
            window._status_label.setText(
                f"{replacement_field_name} changed from {original_mark_id} "
                f"to {replacement_mark_id}."
            )
            set_caption(
                "5 / 8",
                "Change a field's local mark",
                f"Choose {replacement_mark_id} in Local Mark; the link and CON "
                "preview update immediately.",
            )

        capture_scene(
            5.8,
            "5 / 8",
            "Change a field's local mark",
            f"Select {replacement_field_name}; its current assignment is "
            f"{original_mark_id}.",
            setup_replacement,
            animate_replacement,
        )

        reorder_state = {"done": False}

        def setup_reorder() -> None:
            reorder_state["done"] = False
            window._right_tabs.setCurrentWidget(window._field_table)
            previous = window._field_table._sort_combo.blockSignals(True)
            window._field_table._sort_combo.setCurrentText("Manual")
            window._field_table._sort_combo.blockSignals(previous)
            window._field_table._table.selectRow(4)
            window._canvas.fit_all()

        def animate_reorder(progress: float) -> None:
            if progress >= 0.45 and not reorder_state["done"]:
                reorder_state["done"] = True
                window._field_table._sort_combo.setCurrentText("Snake")
                window._status_label.setText(
                    "Snake order applied — mark assignments stayed with their fields."
                )

        capture_scene(
            4.2,
            "6 / 8",
            "Organize the exposure sequence",
            "Manual, Snake, Raster, and Radial keep every edited assignment attached.",
            setup_reorder,
            animate_reorder,
        )

        class PointerEvent:
            def __init__(self, position: QPointF):
                self._position = position

            @staticmethod
            def button():
                return Qt.MouseButton.LeftButton

            def position(self):
                return self._position

            def accept(self) -> None:
                return None

        zoom_state = {
            "pressed": False,
            "released": False,
            "pan": False,
            "start": QPointF(),
            "end": QPointF(),
        }

        def setup_zoom() -> None:
            zoom_state["pressed"] = False
            zoom_state["released"] = False
            zoom_state["pan"] = False
            window._fit_view_button.click()
            window._zoom_area_button.click()
            viewport = window._canvas.viewport().rect()
            zoom_state["start"] = QPointF(
                viewport.width() * 0.23,
                viewport.height() * 0.20,
            )
            zoom_state["end"] = QPointF(
                viewport.width() * 0.72,
                viewport.height() * 0.73,
            )

        def animate_zoom(progress: float) -> None:
            if progress >= 0.12 and not zoom_state["pressed"]:
                zoom_state["pressed"] = True
                window._canvas.mousePressEvent(PointerEvent(zoom_state["start"]))
            if zoom_state["pressed"] and not zoom_state["released"]:
                drag_progress = min(1.0, max(0.0, (progress - 0.12) / 0.34))
                start = zoom_state["start"]
                end = zoom_state["end"]
                current = QPointF(
                    start.x() + (end.x() - start.x()) * drag_progress,
                    start.y() + (end.y() - start.y()) * drag_progress,
                )
                window._canvas.mouseMoveEvent(PointerEvent(current))
            if progress >= 0.48 and not zoom_state["released"]:
                zoom_state["released"] = True
                window._canvas.mouseReleaseEvent(PointerEvent(zoom_state["end"]))
            if progress >= 0.65 and not zoom_state["pan"]:
                zoom_state["pan"] = True
                window._pan_button.click()
            if zoom_state["pan"]:
                pan_progress = min(1.0, (progress - 0.65) / 0.35)
                horizontal = window._canvas.horizontalScrollBar()
                vertical = window._canvas.verticalScrollBar()
                horizontal.setValue(
                    round(horizontal.minimum()
                          + (horizontal.maximum() - horizontal.minimum())
                          * 0.65 * pan_progress)
                )
                vertical.setValue(
                    round(vertical.minimum()
                          + (vertical.maximum() - vertical.minimum())
                          * 0.40 * pan_progress)
                )

        capture_scene(
            3.8,
            "7 / 8",
            "Inspect dense layouts",
            "Use Zoom Area, the mouse wheel, zoom buttons, Pan, and both scrollbars.",
            setup_zoom,
            animate_zoom,
        )

        save_state = {"saved": False}
        output_con = temporary_path / "synthetic_output.CON"

        def setup_save() -> None:
            save_state["saved"] = False
            window._pan_button.click()
            window._fit_view_button.click()
            window._right_tabs.setCurrentWidget(window._field_table)
            output_con.write_text("previous synthetic version\n", encoding="utf-8")
            window._status_label.setText(
                "Review the generated CON preview before saving."
            )
            window._update_workflow_state()

        def animate_save(progress: float) -> None:
            if progress >= 0.45 and not save_state["saved"]:
                save_state["saved"] = True
                if not window._file_editor.save(str(output_con)):
                    raise RuntimeError("Could not save the synthetic CON demonstration.")
                window._update_workflow_state()
                window._status_label.setText(
                    "Synthetic CON saved atomically with an automatic backup."
                )

        capture_scene(
            3.8,
            "8 / 8",
            "Review and save the CON",
            "Review mark assignments and field order; replacement creates a backup.",
            setup_save,
            animate_save,
        )

        def setup_final() -> None:
            window._status_label.setText(
                "PREPARATION ONLY — operator verification is required before exposure"
            )

        capture_scene(
            3.2,
            "Complete",
            "Operator review remains essential",
            "Verify the final CON, alignment strategy, units, and process settings.",
            setup_final,
        )

        window.close()
        app.processEvents()

        frame_pattern = str(frame_directory / "frame_%05d.png")
        _run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                str(args.fps),
                "-i",
                frame_pattern,
                "-vf",
                "scale=1280:800:flags=lanczos,format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-movflags",
                "+faststart",
                str(mp4_path),
            ]
        )
        _run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(mp4_path),
                "-filter_complex",
                (
                    "[0:v]fps=8,scale=960:600:flags=lanczos,split[s0][s1];"
                    "[s0]palettegen=max_colors=96:stats_mode=diff[p];"
                    "[s1][p]paletteuse=dither=bayer:bayer_scale=3:"
                    "diff_mode=rectangle"
                ),
                "-loop",
                "0",
                str(gif_path),
            ]
        )

    print(mp4_path)
    print(gif_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
