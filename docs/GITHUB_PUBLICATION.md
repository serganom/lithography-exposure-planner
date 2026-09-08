# GitHub Publication Material

Ready-to-copy repository metadata, requirements, and release text for
Lithography Exposure Planner 0.3.0 beta.

## Repository name

`lithography-exposure-planner`

## GitHub About

Cross-platform desktop tool for detecting local alignment marks in GDSII,
assigning them to exposure fields, and safely organizing CRESTEC CON jobs.

## Publication media

- Embed the
  [synthetic GIF walkthrough](media/lithography-exposure-planner-demo.gif)
  in the GitHub README.
- Attach the
  [H.264 MP4 walkthrough](media/lithography-exposure-planner-demo.mp4)
  to the LinkedIn launch post.
- Use the prepared [captions, timing, and alt text](DEMO_WALKTHROUGH.md).

Both files demonstrate the application with synthetic data only. The paced
walkthrough explicitly shows a field's local-mark assignment being replaced
before the exposure sequence is reorganized.

## Short project summary

Lithography Exposure Planner helps prepare electron-beam lithography jobs that
contain many local alignment marks and exposure fields. It combines GDSII
cross-mark detection, explicit field-to-mark assignment, visual inspection,
and field-sequence editing in one English desktop interface.

The application is particularly useful for transistor layouts, where a large
number of local marks and fields can make manual assignment difficult, but it
is not limited to transistor devices. The same workflow applies to any EBL
topology with many local marks and exposure fields.

## Extended description

The guided workflow follows five operator-visible steps:

1. Open the GDSII layout.
2. Open the source CON job.
3. Detect local R23 marks on an exact GDS layer/datatype.
4. Assign marks to fields and organize the exposure sequence.
5. Review and save the resulting CON file.

Every detected GDS cross remains available in the mark catalog, including
positions that were not already present in the source CON. A field can be
assigned from a distance-sorted drop-down, by an explicit Mark Catalog action,
or by selecting the field and clicking a green mark in the layout view.
Selecting a catalog row alone never changes the job.

For dense layouts, the main view provides Pan, a rectangular Zoom Area
magnifier, bounded zoom-in/out controls, Fit, a magnification indicator, and
always-visible horizontal and vertical scrollbars.

The current implementation targets the CRESTEC CABL-9500C workflow and a
fail-closed subset of CON syntax. It prepares files only: it does not control
the lithography system, acquire a physical alignment signal, move the stage,
set process parameters, or start exposure. Every generated job must be
reviewed by an operator.

The shared Python/PyQt6 source targets macOS and Windows. macOS on Apple
Silicon has been tested locally. Native Windows x64 and macOS Intel
interactive validation are still pending.

Support for another EBL system requires a dedicated and validated adapter for
that system's job format and alignment semantics. The presence of an R23-like
command alone does not establish compatibility.

## Suggested GitHub topics

`electron-beam-lithography`, `ebl`, `gdsii`, `alignment-marks`,
`con-file`, `pyqt6`, `nanofabrication`, `crestec`,
`exposure-planning`, `cross-platform`

## Functional requirements

1. Load GDSII and display exact layer/datatype pairs.
2. Detect compatible one-piece and two-rectangle cross centers on a selected
   layer/datatype.
3. Parse only the supported CON subset and fail closed on unknown or ambiguous
   commands.
4. Preserve existing CON mark IDs, coordinates, field assignments, and source
   text until the user explicitly saves.
5. Keep every detected GDS position available regardless of GDS/CON load order.
6. Assign a local R23 mark through a field drop-down, an explicit catalog
   action, or a canvas click after selecting a target field.
7. Ensure selecting a Mark Catalog row only highlights the mark.
8. Show assigned field names in the read-only Mark Catalog.
9. Reorder fields manually or with Snake, Raster, and Radial (center-out)
   methods while preserving field-to-mark relationships.
10. Provide Pan, rectangular Zoom Area, zoom-in/out, mouse-wheel zoom, Fit,
    a magnification indicator, and visible horizontal/vertical scrollbars.
11. Preview the regenerated CON before writing it.
12. Save atomically and create a backup when replacing an existing CON file.
13. Run from the same Python/PyQt6 source tree on macOS and Windows.

## Non-functional requirements

- All user-visible application text and public documentation are English.
- Navigation actions never modify fields, marks, assignments, or CON text.
- The source CON file remains unchanged until explicit Save CON.
- Unsafe regeneration is blocked with a clear error instead of silently
  dropping unsupported content.
- Production GDS/CON files, process recipes, and internal filesystem paths are
  excluded from publication.
- Logs are written to a user-writable platform-specific directory.
- Native packages are built and validated on their target operating system.
- Equipment and process compatibility claims are limited to verified evidence.

## Acceptance criteria for 0.3.0 beta

- [x] A five-step English workflow is visible at the top of the window.
- [x] Fields and Order is the primary working tab.
- [x] Local mark generation is limited to the supported R23 command.
- [x] Exact GDS layer/datatype selection is available.
- [x] All detected GDS crosses remain selectable after loading a CON.
- [x] Mark Catalog selection requires an explicit assignment action.
- [x] Field reordering preserves mark assignments.
- [x] Pan, Zoom Area, zoom buttons, Fit, magnification, and both scrollbars are
      available in the layout view.
- [x] Existing CON files are saved atomically with a backup.
- [x] The 54-test automated suite passes locally on macOS arm64.
- [ ] Native Windows x64 interactive validation.
- [ ] Native macOS Intel interactive validation.
- [ ] Validation on the exact target CRESTEC CABL-9500C configuration.
- [ ] Rights-holder approval and selection of a project license.

## Release notes draft

### Lithography Exposure Planner 0.3.0 beta

- Introduced a clear five-step English exposure-job workflow.
- Made Fields and Order the primary workspace and Mark Catalog a read-only
  overview with explicit assignment.
- Preserved all detected GDS crosses for selection, regardless of file-load
  order.
- Added exact GDS layer/datatype selection and supported local R23 handling.
- Added manual, Snake, Raster, and Radial field-sequence organization while
  keeping assignments attached to fields.
- Added Pan and rectangular Zoom Area modes, bounded zoom controls, Fit,
  magnification display, and always-visible layout scrollbars.
- Added visible GDS, CON, field, mark, and assignment summaries.
- Kept source CON files unchanged until explicit saving and retained atomic
  saving with automatic backups.
- Translated the active interface, dialogs, errors, and public documentation
  into English.
- Expanded the local automated suite to 54 tests, including magnifier
  interaction and GUI cleanup.

The application prepares exposure-job files only. Verify the final CON,
alignment strategy, units, and all process parameters before exposure.

## Building and validation

```sh
python -m pip install -r requirements.txt -r requirements-dev.txt -c constraints-build.txt
python -m pytest
python scripts/build_app.py
```

Use `scripts/build_macos.sh` on macOS and
`scripts\build_windows.bat` on Windows. Versioned output is written to
`dist/0.3.0`.

See [cross-platform support](CROSS_PLATFORM.md),
[verification](VERIFICATION.md), and the
[publication checklist](PUBLICATION_CHECKLIST.md).
