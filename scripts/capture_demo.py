"""Render an application-only screenshot with synthetic data (no desktop capture)."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/images/demo.png"))
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import numpy as np
    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QApplication

    from app.main_window import MainWindow
    from app_info import APP_NAME, APP_VERSION

    app = QApplication([])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    project_root = Path(__file__).resolve().parents[1]
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    saved = []

    with tempfile.TemporaryDirectory(prefix="litho-demo-") as temporary:
        settings = QSettings(
            str(Path(temporary) / "preferences.ini"), QSettings.Format.IniFormat
        )
        window = MainWindow(settings=settings)
        window.resize(1680, 1000)
        window._dir_tree.set_root(str(project_root / "examples"))
        window._on_tree_con_clicked(str(project_root / "examples" / "sample.CON"))
        window._right_tabs.setCurrentWidget(window._field_table)
        polygons = [
            np.array([[x - 0.03, 0.49], [x + 0.03, 0.49],
                      [x + 0.03, 0.51], [x - 0.03, 0.51]])
            for x in (-1.0, 1.0)
        ]
        window._gds_layer_combo.blockSignals(True)
        window._gds_layer_combo.addItem("L82/0 (synthetic)", (82, 0))
        window._gds_layer_combo.setCurrentIndex(1)
        window._gds_layer_combo.blockSignals(False)
        window._canvas.set_gds_layer(82, polygons)
        window._workflow.set_state(
            gds_path="synthetic_layout.gds",
            con_path=str(project_root / "examples" / "sample.CON"),
            field_count=len(window._current_con.fields),
            mark_count=len(window._current_con.marks),
            assigned_count=sum(
                bool(field.mark_id) for field in window._current_con.fields
            ),
            modified=False,
        )
        window._status_label.setText(
            "SYNTHETIC DEMO — not an exposure job"
        )
        window.show()
        window._canvas.fit_all()

        def capture():
            saved.append(window.grab().save(str(destination)))
            window.close()
            app.quit()

        QTimer.singleShot(600, capture)
        app.exec()

    if saved != [True]:
        raise RuntimeError("Could not save the demonstration screenshot")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
