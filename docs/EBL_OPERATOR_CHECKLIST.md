# Pre-Exposure EBL Job Check

The application helps prepare a job file; it does not replace process or
operator verification.

## Known for this project

- Primary layout input: GDSII.
- Target working file: CON.
- Initial target system: CRESTEC CABL-9500C.
- Scope: local-mark assignment and exposure-field sequencing.
- Applicable to any layout with many local marks and fields; transistor
  structures are one example.
- No direct hardware control is performed.

## Confirm for every job

- [ ] Sample ID and layout revision.
- [ ] GDSII user unit and database unit.
- [ ] Intended exposure layers and excluded layers.
- [ ] Exact local-mark layer/datatype and mark strategy.
- [ ] Coordinate origin, axis direction, sample orientation, rotation, and reflection.
- [ ] Write-field size and acceptable stitching risk.
- [ ] CON format version and target-tool software version.
- [ ] Exposure-field sequence matches the intended process route.
- [ ] R23 units, precision, scope, and switching behavior are correct.
- [ ] Every automatically selected nearest mark is technologically appropriate.

Adaptation to another EBL system requires a separate compatibility review:
[CON/R23 compatibility](TOOL_COMPATIBILITY.md).

## Parameters not defined by the application

Obtain every value below from an approved process recipe:

- Beam energy: TBD.
- Current or aperture: TBD.
- Dose or dose classes: TBD.
- Exposure step size: TBD.
- Resist, thickness, spin/bake, and developer: TBD.
- Proximity-effect correction: TBD.
- Conductive coating: TBD.

## Before Exposure

- [ ] Compare the source and final CON, including commands outside field blocks.
- [ ] Verify every local-mark coordinate and field assignment.
- [ ] Verify units, coordinate signs, rotation, and reflection.
- [ ] Verify the number and order of exposure fields.
- [ ] Verify each R23 transition after field reordering.
- [ ] Confirm nearest-mark assignment did not violate the alignment strategy.
- [ ] Confirm the correct GDSII file and layout revision are open.
- [ ] Confirm exposure parameters against the approved recipe.
- [ ] Load the result in the target-tool software in review mode before exposure.
- [ ] Archive the source CON, final CON, and preparation log.
