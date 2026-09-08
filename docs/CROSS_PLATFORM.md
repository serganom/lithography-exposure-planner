# Cross-Platform Support

Version 0.3.0 uses one Python/PyQt6 codebase. Native packages must be built
separately on each target operating system and architecture.

## Status

| Target | Build path | Validation |
| --- | --- | --- |
| macOS Apple Silicon | PyInstaller `.app` | Locally tested on macOS 13.7.8 |
| macOS Intel | separate PyInstaller `.app` | CI/build configured; native validation pending |
| Windows 10/11 x64 | PyInstaller one-directory bundle | CI/build configured; native validation pending |

A successful CI configuration is not the same as an interactive validation on
the target machine.

## Source requirements

- Python 3.10 or newer.
- Reference build interpreter: Python 3.12.
- Dependencies: `requirements.txt`.
- Development/build dependencies: `requirements-dev.txt`.
- Reproducible reference versions: `constraints-build.txt`.

PyQt6, gdspy, and NumPy contain platform-specific components. Never copy
`.venv` between operating systems or CPU architectures.

## Running from source

macOS:

```sh
./run.sh
```

or open `run.command`.

Windows:

```bat
run.bat
```

The bootstrap creates a local `.venv`, installs dependencies, and launches
the GUI. A prepared environment can run `python src/main.py` directly.

## Building native packages

Build on the target system. PyInstaller does not cross-compile.

macOS:

```sh
./scripts/build_macos.sh
```

Windows:

```bat
scripts\build_windows.bat
```

Equivalent command in a prepared Python 3.12 environment:

```sh
python -m pip install -r requirements.txt -r requirements-dev.txt -c constraints-build.txt
python scripts/build_app.py
```

Output is written to `dist/0.3.0` by default. The build script runs tests and
Ruff, creates the native bundle, then performs an isolated startup smoke test
without `PYTHONPATH` or `PYTHONHOME`. It also creates a ZIP containing the
complete package.

The Windows executable must remain beside its `_internal` directory. The
macOS `.app` directory must remain intact.

## CI matrix

Configured GitHub Actions targets:

- `windows-2022` x64;
- `macos-15` arm64;
- `macos-15-intel` x64.

The manual package workflow builds platform-specific ZIP artifacts. It does not
publish a GitHub Release automatically.

## Platform behavior covered by tests

- Platform-appropriate writable log directories.
- Unicode and spaces in file paths.
- UTF-8 BOM and CRLF CON input.
- Atomic save and backup behavior.
- Startup without a terminal stream.
- Native-package command construction.
- Shared English workflow widgets and standard Qt shortcuts.

## Required native acceptance

Before claiming tested Windows or Intel support:

1. Start the packaged application without a terminal.
2. Open representative GDS and CON files.
3. Detect marks on an exact layer/datatype.
4. Reassign several fields manually.
5. Reorder fields and verify assignments remain attached.
6. Save to a new CON and compare source/result.
7. Verify the backup and application log.
8. Close and restart the package.

## Packaging and signing

The locally verified macOS package used ad-hoc signing. Public distribution may
require Developer ID signing and notarization. Windows public distribution may
require code signing. Confirm third-party license obligations before any
binary release.

See [verification](VERIFICATION.md) and the
[publication checklist](PUBLICATION_CHECKLIST.md).
