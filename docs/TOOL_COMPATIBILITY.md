# EBL Tool Compatibility and the R23 Command

## Confirmed scope

- The original workflow targets a CRESTEC CABL-9500C installation.
- The application detects geometric mark centers in GDSII, links marks to
  exposure fields, and prepares field order in CON.
- Physical mark acquisition is performed by the EBL system. This application
  does not inspect detector signals, move the stage, or start exposure.
- No other EBL model has been validated by this project.

## R23 representation

The user's descriptive notation was:

```text
R23 coord X (0.00), coord Y (0.00);
```

The current parser accepts the numeric form:

```text
R23 0.000, 0.000;
```

This is a synthetic syntax example, not a production coordinate. The current
model interprets CON coordinates as millimetres. It writes marks to 0.001 mm
and fields to 0.00001 mm. Confirm units and required precision using the
documentation for the exact target system and software version.

If a target system requires literal labels such as `coord X (...)`, another
grammar, or a different job format, it needs a dedicated parser/export adapter.

## Current semantic assumption

An R23 command makes one local mark active for following fields until another
mark command appears. When the sequence returns to a previously used mark, the
generator emits R23 again. Assignments come from the explicit application
model, not from distance alone.

This rule must be confirmed with the target controller manual and a known-good
CON example. The geometrically nearest mark is not necessarily the correct
process mark.

## Adapting to another EBL system

Directly transferring a CON file and adapting this application are different
tasks. Direct transfer requires compatible syntax and semantics. Adaptation to
another job language requires an exporter and may require a richer alignment
model, for example multiple marks per field.

R23 is neither required nor sufficient for future adaptation. Validate:

1. Meaning, acquisition timing, and scope of the local-alignment command.
2. Units, origin, axis direction, signs, and coordinate precision.
3. Field syntax and its link to layout data.
4. Header/end commands and all mandatory job metadata.
5. Mark persistence, switching, and reset behavior after field reordering.
6. Global versus local alignment and their required sequence.
7. Physical mark geometry and detection requirements.
8. Import of a controlled test job by the target software.

No adapter for another EBL system is implemented. Universal compatibility is
not claimed.

## Missing evidence

- Specifications and software versions for other EBL systems: TBD.
- Verified native job examples for those systems: TBD.
- Acceptance results from another controller: TBD.

Unknown CON commands block automatic regeneration so that process-significant
instructions are not silently discarded.

## Before Exposure

- [ ] Confirm coordinate units and precision.
- [ ] Confirm every local mark belongs to the intended fields.
- [ ] Verify R23 transitions after reordering.
- [ ] Compare headers, global commands, and field count with the source job.
- [ ] Validate the final file in the target-tool software before exposure.
