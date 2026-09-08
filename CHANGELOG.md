# Changelog

## 0.3.0

- Added a clear five-step English exposure-job workflow.
- Made Fields & Order the primary workspace and added visible job-status summaries.
- Made Mark Catalog assignment explicit; selecting a mark now only highlights it.
- Replaced editable field-index lists with read-only assigned field names.
- Added clear layout controls, a field/mark/link legend, and descriptive help text.
- Added Pan and rectangular Zoom Area modes, bounded zoom controls, Fit, a
  magnification indicator, and always-visible layout scrollbars.
- Removed transistor-specific Gate/Cap filters from the general file browser.
- Translated all active UI strings, dialogs, errors, and public documentation to English.
- Added regression tests for workflow structure and explicit catalog assignment.


## 0.2.4

- Removed unsupported R24/R25 choices; detected local marks always use R23.
- Preserved the GDS-detected mark catalog when a CON is loaded, so loading
  GDS and CON in either order exposes every detected cross for assignment.
- Kept global R2 commands separate from local R23 cross matching.
- Removed the legacy Layers+Extract action from the application interface.
- Kept CON text unchanged until the user explicitly changes an assignment.


## 0.2.3

- Selecting a field row now starts manual mark-assignment mode.
- Added a distance-sorted Mark ID drop-down with coordinates for every field.
- Made green mark crosses easier to click while assigning and added a visible
  crosshair cursor for assignment mode.
- Restored GDS layer information used by Layers+Extract.


## 0.2.2

- Added exact GDS layer/datatype selection, such as 500/0.
- Added geometric recognition of one-polygon and two-rectangle cross marks.
- Removed the false 10 µm rejection for recognized cross geometry.
- Preserved existing CON mark IDs, coordinates, and field assignments during GDS import.
- Added a warning when a CON mark does not coincide with a detected GDS cross.
## 0.2.1

- Added shared environment bootstrap and native build/test/archive scripts for macOS and Windows.
- Added Windows x64 and macOS arm64/x64 CI plus manual desktop-package builds.
- Added pinned reference build constraints and platform-specific setup instructions.
- Used the system monospace font and standard Qt keyboard shortcuts.
- Added Unicode/CRLF/BOM, file-lock failure, console-free startup, and platform-path tests.
- Verified reordering 240 synthetic fields with 40 marks preserves all assignments.
- Clarified the application is useful for any mark/field-heavy EBL job; transistors are one example.
- Documented conditional adaptation to compatible R23/CON workflows, without universal tool claims.
- macOS arm64 is locally tested; native Windows and macOS Intel validation remain pending.

## 0.2.0

- Added rotating application logs and visible crash reporting.
- Added a headless startup smoke test.
- Added atomic CON saving with automatic .bak backups.
- Added a warning when closing with unsaved CON changes.
- Restored window geometry between sessions.
- Fixed GDS reference rotation and x-reflection handling.
- Fixed polygon-area calculation for non-closed vertex arrays.
- Added reproducible tests, launchers, packaging metadata, and CI configuration.

- Fixed mark reuse after intervening fields (A → B → A).
- Normalized imported GDS units; preserved units when extracting modules.
- Blocked automatic regeneration of unsupported or ambiguous CON source.
- Protected unsaved changes when switching/dropping CON files.
- Synchronized edited CON headers and canvas field size.
- Added native crash traces and isolated smoke-test preferences.
