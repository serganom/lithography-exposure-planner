"""Build and smoke-test a native macOS or Windows bundle (not a cross-compiler)."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app_info import APP_NAME, APP_SLUG, APP_VERSION  # noqa: E402

CHECK_PATHS = [
    "src",
    "tests/test_core.py",
    "tests/test_smoke.py",
    "tests/test_regressions.py",
    "tests/test_platform.py",
    "scripts/bootstrap.py",
    "scripts/build_app.py",
    "scripts/capture_demo.py",
]


def platform_tag(platform_name: str, machine: str) -> str:
    architecture = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        machine.lower()
    )
    if platform_name == "win32" and architecture == "x64":
        return "windows-x64"
    if platform_name == "darwin" and architecture in {"x64", "arm64"}:
        return f"macos-{architecture}"
    raise ValueError("Native builds currently target Windows x64 and macOS arm64/x64 only.")


def bundle_path(output_dir: Path, platform_name: str) -> Path:
    return output_dir / (f"{APP_NAME}.app" if platform_name == "darwin" else APP_NAME)


def executable_path(output_dir: Path, platform_name: str) -> Path:
    bundle = bundle_path(output_dir, platform_name)
    if platform_name == "darwin":
        return bundle / "Contents" / "MacOS" / APP_NAME
    return bundle / f"{APP_NAME}.exe"


def pyinstaller_command(output_dir: Path, work_dir: Path, platform_name: str) -> list[str]:
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
        "--name", APP_NAME, "--distpath", str(output_dir), "--workpath", str(work_dir),
        "--specpath", str(work_dir), "--paths", str(ROOT / "src"),
    ]
    for package in ("PyQt6", "gdspy", "numpy"):
        command += ["--copy-metadata", package]
    if platform_name == "darwin":
        command += ["--osx-bundle-identifier", "local.litho.exposure-planner"]
    return [*command, str(ROOT / "src" / "main.py")]


def verify_bundle(executable: Path) -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUTF8"] = "1"
    with tempfile.TemporaryDirectory(prefix="litho smoke ") as directory:
        log_dir = Path(directory) / "Launch Check"
        result = subprocess.run(
            [str(executable), "--smoke-test", "--log-dir", str(log_dir)],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
            check=False,
        )
        log_path = log_dir / "application.log"
        log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        if (
            result.returncode != 0
            or "Main window visible: True" not in log_text
            or "Application stopped with exit code 0" not in log_text
        ):
            raise RuntimeError(f"Bundled smoke test failed ({result.returncode}).\n{result.stderr}\n{log_text}")
    print("Bundled smoke test passed from an independent directory.", flush=True)


def archive_bundle(output_dir: Path, tag: str, platform_name: str) -> Path:
    archive = output_dir / f"{APP_SLUG}-{APP_VERSION}-{tag}.zip"
    bundle = bundle_path(output_dir, platform_name)
    if platform_name == "darwin":
        # ditto preserves .app symlinks and executable permissions.
        subprocess.run(
            ["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(archive)],
            check=True,
        )
    else:
        # Keep the entire onedir distribution, including _internal and Qt plugins.
        shutil.make_archive(str(archive.with_suffix("")), "zip", output_dir, bundle.name)
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / APP_VERSION)
    args = parser.parse_args(argv)
    try:
        tag = platform_tag(sys.platform, platform.machine())
        output_dir = args.output_dir.expanduser().resolve()
        work_dir = ROOT / "build" / tag
        output_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT, check=True)
        subprocess.run([sys.executable, "-m", "ruff", "check", *CHECK_PATHS], cwd=ROOT, check=True)
        subprocess.run(pyinstaller_command(output_dir, work_dir, sys.platform), cwd=ROOT, check=True)
        verify_bundle(executable_path(output_dir, sys.platform))
        if sys.platform == "darwin":
            subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", str(bundle_path(output_dir, sys.platform))],
                check=True,
            )
        archive = archive_bundle(output_dir, tag, sys.platform)
        print(f"Native bundle: {bundle_path(output_dir, sys.platform)}")
        print(f"Local test archive: {archive}")
        print("Not a public release: review licenses and distribution rights before sharing.")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
