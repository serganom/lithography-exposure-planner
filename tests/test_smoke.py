from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_application_starts_and_stops_cleanly(tmp_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "src" / "main.py"),
            "--smoke-test",
            "--log-dir",
            str(tmp_path),
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / "application.log").read_text(encoding="utf-8")
    assert "Application stopped with exit code 0" in log_text
