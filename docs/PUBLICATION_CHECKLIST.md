# Publication Checklist

The project is prepared locally. The repository and release packages have not
yet been published.

## Rights-holder decisions

- [ ] Confirm the rights holder and complete author list.
- [ ] Confirm source disclosure is permitted under invention/IP filings,
  employment agreements, contracts, and institutional policy.
- [ ] Select a project license; no LICENSE file has been created automatically.
- [ ] Verify compatibility with PyQt6 and all other dependency licenses.
  PyQt is available under GPL v3 or a commercial license:
  [Riverbank](https://www.riverbankcomputing.com/software/pyqt/).
- [ ] Include required third-party notices before publishing binaries.

## Repository content

- [ ] Publish only files not excluded by `.gitignore`.
- [ ] Do not upload `.venv`, `build`, `dist`, local `.git`, or caches.
- [ ] Do not publish production GDS/CON files, process recipes, doses, or
  internal filesystem paths.
- [ ] Confirm `docs/images/demo.png` contains synthetic data only and shows
  the current Pan, Zoom Area, Fit, and scrollbar controls.
- [ ] Run the complete automated suite and record the current 54-test result.
- [ ] Use the GIF in the GitHub README and upload the MP4 directly to LinkedIn.
- [ ] Review the prepared timing, caption, and alt text in
  `docs/DEMO_WALKTHROUGH.md`.
- [ ] Note that version 0.3.0 differs from source fragments prepared for any
  earlier software-registration application.
- [ ] Replace the LinkedIn GitHub placeholder with the published repository URL.
- [ ] Complete native Windows x64 and macOS Intel validation before claiming
  those platforms are tested.
- [ ] Describe the broad use case: layouts with many marks and fields;
  transistor structures are an example, not a limitation.
- [ ] Do not claim compatibility with another EBL tool based only on R23.

## Equipment validation

No exposure was performed during software verification. An operator must
validate the supported CON subset and the exact CRESTEC CABL-9500C
configuration. See the [operator checklist](EBL_OPERATOR_CHECKLIST.md).
