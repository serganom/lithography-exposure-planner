# Local Verification — Version 0.3.0

Date: 2026-09-07. Status: beta. Automated checks use synthetic data; selected
interface-model checks also use the user-provided job files in read-only mode.

## Reference environment

- macOS 13.7.8 (22H730), Apple Silicon / arm64.
- Python 3.12.7.
- PyQt6 6.11.0, Qt 6.11.2, PyQt6-sip 13.12.0.
- gdspy 1.6.13, NumPy 2.5.2.
- PyInstaller 6.22.2.

Reference build versions are pinned in `constraints-build.txt`. Windows and
macOS Intel still require native validation.

## Results

| Check | Result |
| --- | --- |
| Automated tests | 54 passed |
| Ruff on source, tests, and scripts | Passed |
| Source startup and clean shutdown | Passed |
| Windowed Windows-like run without stdout/stderr | Simulated successfully on macOS |
| UTF-8 BOM, CRLF, Unicode, and spaces in CON paths | Passed |
| Atomic replacement failure | Source preserved and temporary file removed |
| Manual mark reassignment | Drop-down, explicit catalog action, and canvas click passed |
| Mark-catalog selection | Does not change a field until explicit assignment |
| GDS/CON load order | Both orders preserve detected marks and source assignments |
| 240 fields / 40 marks reorder | Every assignment preserved |
| English guided workflow | Five steps and English panels verified |
| Native macOS arm64 app smoke test | Passed in the prior 0.2.x build flow |
| codesign deep/strict verification | Passed for the prior local ad-hoc build |

Path and parameter tests for Windows validate logic only; they do not replace a
native Windows run.

## Still pending

- Remote CI and packaged 0.3.0 builds.
- Interactive Windows 10/11 x64 validation.
- Interactive macOS Intel validation.
- Exposure on the exact CRESTEC CABL-9500C configuration.
- Compatibility with other EBL tools or CON/R23 variants.
- Full nested-mark hierarchy and CellArray validation.
- Performance measurements on large production layouts.

A local ad-hoc macOS signature is not a Developer ID signature. Notarization
and a public binary release have not been completed.

Before equipment use, follow the
[EBL operator checklist](EBL_OPERATOR_CHECKLIST.md). Before distribution,
follow the [publication checklist](PUBLICATION_CHECKLIST.md).
