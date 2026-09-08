"""Prepare a local environment and launch the same application on each OS."""

from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def environment_python(root: Path, platform_name: str | None = None) -> Path:
    if (platform_name or sys.platform) == "win32":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def ensure_environment(root: Path) -> Path:
    python = environment_python(root)
    environment = root / ".venv"
    if not python.is_file():
        if environment.exists():
            raise RuntimeError(
                "The existing .venv is incomplete or belongs to another OS. "
                "Use a fresh source folder; never copy .venv between computers."
            )
        print("Creating a local Python environment...", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    return python


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Build a native desktop bundle")
    args, forwarded = parser.parse_known_args(argv)
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 or newer is required; use Python 3.12 for native builds.")
    if args.build and sys.version_info[:2] != (3, 12):
        parser.error("Pinned native builds require Python 3.12.")

    try:
        python = ensure_environment(ROOT)
        probe = subprocess.run(
            [str(python), "-c", "import PyQt6.QtWidgets, gdspy, numpy"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if args.build or probe.returncode:
            print(
                "Installing dependencies. Source builds of gdspy require a C++ compiler: "
                "Visual Studio Build Tools on Windows, Xcode Command Line Tools on macOS.",
                flush=True,
            )
            command = [str(python), "-m", "pip", "install", "-r", "requirements.txt"]
            if args.build:
                command += ["-r", "requirements-dev.txt", "-c", "constraints-build.txt"]
            subprocess.run(command, cwd=ROOT, check=True)
        entry = ROOT / "scripts" / "build_app.py" if args.build else ROOT / "src" / "main.py"
        return subprocess.run([str(python), str(entry), *forwarded], cwd=ROOT, check=False).returncode
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        print("See docs/CROSS_PLATFORM.md for platform prerequisites.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
