# LinkedIn post

## Ready-to-publish version

Preparing a dense electron-beam lithography job should not require manually
tracing dozens of local alignment marks, checking which mark belongs to each
field, and rebuilding the exposure sequence line by line.

That becomes especially difficult in transistor layouts, but the same problem
appears in any EBL topology with many local marks and exposure fields.

I developed **Lithography Exposure Planner** to bring this preparation workflow
into one visual desktop application. Version 0.3.0 beta now guides the operator
through five clear steps:

1. Open the GDSII layout.
2. Open the source CON job.
3. Detect local R23 marks on the selected GDS layer/datatype.
4. Assign marks and organize the field sequence.
5. Review and save the resulting CON file.

The attached 35-second walkthrough uses synthetic data only and demonstrates
this complete sequence with short English captions. The key preparation stages
are intentionally slower, including an explicit change from one local mark to
another for a selected field.

The application can:

- detect centers of compatible cross-shaped marks in GDSII;
- keep all detected crosses available, even when they were not already listed
  in the source CON;
- assign marks explicitly from a field list, the Mark Catalog, or the layout;
- suggest the nearest mark as an optional starting point;
- reorder fields manually or with Snake, Raster, and Radial paths while
  preserving assignments;
- navigate dense layouts with Pan, a rectangular Zoom Area magnifier,
  zoom-in/out controls, Fit, and visible scrollbars;
- save supported CON files atomically and create a backup.

The goal is to reduce repetitive preparation work and make field-to-mark
relationships and exposure order easier to inspect before going to the tool.

The current implementation targets the **CRESTEC CABL-9500C** workflow and a
validated subset of CON syntax. It does not control the lithography system,
set exposure parameters, or replace operator verification. Support for another
EBL platform would require a dedicated, tested adapter for that platform's job
format and alignment procedure; an R23-like command alone is not enough to
claim compatibility.

The shared Python/PyQt6 codebase targets macOS and Windows. macOS on Apple
Silicon has been tested locally, while native Windows validation is still
pending.

I am preparing the project for public testing and would value feedback from
the EBL and nanofabrication community. How do you currently manage local-mark
assignment and field sequencing in complex jobs?

GitHub: [add repository URL]

#ElectronBeamLithography #EBL #Nanofabrication #GDSII #Python #PyQt6
