from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

import runtime
from app_info import APP_NAME
from core.con_parser import ConParser
from models.con_file import ConFileData
from models.field import ExposureField
from models.mark import AlignmentMark
from utils import file_io

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("platform_name", ["darwin", "win32", "linux"])
def test_log_directory_is_platform_specific(monkeypatch, tmp_path, platform_name):
    monkeypatch.setattr(runtime.sys, "platform", platform_name)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local App Data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    expected = {
        "darwin": Path.home() / "Library" / "Logs" / APP_NAME,
        "win32": tmp_path / "Local App Data" / APP_NAME / "Logs",
        "linux": tmp_path / "state" / "lithography-exposure-planner" / "logs",
    }
    assert runtime.default_log_dir() == expected[platform_name]


def test_windows_log_directory_falls_back_to_user_home(monkeypatch):
    monkeypatch.setattr(runtime.sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert runtime.default_log_dir() == Path.home() / "AppData" / "Local" / APP_NAME / "Logs"


@pytest.mark.parametrize(
    "platform_name, machine, tag",
    [("win32", "AMD64", "windows-x64"), ("darwin", "arm64", "macos-arm64"),
     ("darwin", "x86_64", "macos-x64")],
)
def test_native_build_configuration(tmp_path, platform_name, machine, tag):
    builder = load_script("build_app")
    assert builder.platform_tag(platform_name, machine) == tag
    command = builder.pyinstaller_command(tmp_path / "dist", tmp_path / "work", platform_name)
    assert "--windowed" in command and "--onedir" in command
    assert ("--osx-bundle-identifier" in command) == (platform_name == "darwin")
    executable = builder.executable_path(tmp_path, platform_name)
    if platform_name == "win32":
        assert executable == tmp_path / APP_NAME / f"{APP_NAME}.exe"
    else:
        assert executable == tmp_path / f"{APP_NAME}.app" / "Contents" / "MacOS" / APP_NAME


def test_unsupported_windows_arm_build_is_not_mislabelled():
    with pytest.raises(ValueError):
        load_script("build_app").platform_tag("win32", "ARM64")


def test_bootstrap_uses_native_venv_paths_and_rejects_foreign_environment(tmp_path):
    bootstrap = load_script("bootstrap")
    assert bootstrap.environment_python(tmp_path, "win32") == tmp_path / ".venv" / "Scripts" / "python.exe"
    assert bootstrap.environment_python(tmp_path, "darwin") == tmp_path / ".venv" / "bin" / "python"
    (tmp_path / ".venv").mkdir()
    with pytest.raises(RuntimeError, match="another OS"):
        bootstrap.ensure_environment(tmp_path)


def test_con_with_bom_crlf_and_unicode_path_roundtrips(tmp_path):
    path = tmp_path / "Transistors µ 01" / "Local Marks Δ.CON"
    path.parent.mkdir()
    original = (
        "\ufeffCZ0.500,50000;\r\nR23 1.250, -2.500;\r\n"
        "PCF;\r\n1,2;\r\nPPF;\r\n1,2;\r\n!END\r\n"
    ).encode("utf-8")
    path.write_bytes(original)
    parser = ConParser()
    con = parser.parse(path)
    parser.write(con)
    result = parser.parse(path)
    assert result.fields[0].name == "F"
    assert result.marks[0].center_x == 1.25
    assert result.marks[0].center_y == -2.5
    assert path.with_suffix(".CON.bak").read_bytes() == original


def test_failed_replace_preserves_original_and_cleans_temporary_file(monkeypatch, tmp_path):
    path = tmp_path / "job.CON"
    path.write_text("original", encoding="utf-8")

    def locked(*args):
        raise PermissionError("File is locked by another process")

    monkeypatch.setattr(file_io.os, "replace", locked)
    with pytest.raises(PermissionError):
        file_io.atomic_write_text(path, "new", create_backup=True)
    assert path.read_text(encoding="utf-8") == "original"
    assert path.with_suffix(".CON.bak").read_text(encoding="utf-8") == "original"
    assert not list(tmp_path.glob(".*.tmp"))


def test_gui_startup_without_console_streams(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    env["QT_QPA_PLATFORM"] = "offscreen"
    command = (
        "import sys; sys.stdout = None; sys.stderr = None; "
        "from main import main; "
        "raise SystemExit(main(['--smoke-test', '--log-dir', sys.argv[1]]))"
    )
    logs = tmp_path / "Windowed Log Ω"
    result = subprocess.run(
        [sys.executable, "-c", command, str(logs)],
        cwd=tmp_path, env=env, capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Application stopped with exit code 0" in (logs / "application.log").read_text(encoding="utf-8")


def test_many_transistor_fields_keep_assigned_mark_after_reordering():
    marks = [AlignmentMark(f"M{i}", center_x=i * 0.01, center_y=-i * 0.02) for i in range(40)]
    fields = [ExposureField(f"F{i:04d}", center_x=i * 0.001, mark_id=f"M{i % 40}") for i in range(240)]
    con = ConFileData(module_name="synthetic_transistors", marks=marks, fields=fields)
    expected = {field.name: (marks[i % 40].center_x, marks[i % 40].center_y) for i, field in enumerate(fields)}
    con.fields = list(reversed(fields[::2])) + fields[1::2]
    result = ConParser().parse_text(ConParser().serialize(con))
    assert [field.name for field in result.fields] == [field.name for field in con.fields]
    for field in result.fields:
        mark = result.find_mark_by_id(field.mark_id)
        assert (mark.center_x, mark.center_y) == pytest.approx(expected[field.name])
