# Tests

The public test suite uses synthetic data only:

- test_core.py: CON parsing, backups, field ordering, nearest-mark assignment,
  polygon area, and transformed GDS mark coordinates.
- test_smoke.py: offscreen application startup and clean shutdown.
- test_regressions.py: repeated mark assignments, non-micron GDS units,
  unsupported CON rejection, GUI controls, manual field-to-mark reassignment,
  exact GDS layer/datatype handling, the English five-step workflow, explicit\n  catalog assignment, file switching, and editor/model sync.
- test_platform.py: native build parameters, log and environment paths,
  UTF-8 BOM/CRLF and Unicode filenames, file-lock failure, console-free startup,
  and reordering 240 fields with 40 marks without losing assignments.

Run python -m pytest. The current local run passes 54 tests on macOS arm64.
Mocked Windows paths and console behavior are not a substitute for Windows
execution. CI is configured for Windows x64 and both macOS architectures;
those remote runs have not yet been performed.

Older diagnostics tied to private GDS/CON datasets remain excluded by
.gitignore and are not part of the public package.
