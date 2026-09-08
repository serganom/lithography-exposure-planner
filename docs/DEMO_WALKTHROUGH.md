# Demo Walkthrough

## Media files

- GitHub GIF:
  [lithography-exposure-planner-demo.gif](media/lithography-exposure-planner-demo.gif)
- LinkedIn MP4:
  [lithography-exposure-planner-demo.mp4](media/lithography-exposure-planner-demo.mp4)

Duration: approximately 35 seconds.

Resolution:

- MP4: 1280 × 800, H.264.
- GIF: 960 × 600, optimized 96-color palette.

The walkthrough contains synthetic GDS/CON data only. It does not show a
production layout, process recipe, internal path, or real exposure job.

## On-screen sequence

| Time | Step | Short explanation |
| --- | --- | --- |
| 0–3 s | Open GDS and CON | Load the layout and source exposure-field job. |
| 3–6 s | Detect R23 marks | Select the exact GDS layer/datatype and detect cross centers. |
| 6–9 s | Review Mark Catalog | Catalog selection highlights a mark without changing the CON. |
| 9–14 s | Assign marks | Assign a local mark to every field and inspect the links. |
| 14–20 s | Change a local mark | Replace FIELD_01 assignment from R23_1 to R23_2 and inspect the updated link and CON preview. |
| 20–24 s | Organize sequence | Apply a field order while edited assignments remain attached. |
| 24–28 s | Inspect layout | Use Zoom Area, Pan, zoom controls, and scrollbars. |
| 28–32 s | Review and save | Review the result, save the CON atomically, and create a backup. |
| 32–35 s | Operator check | Verify alignment, units, and process settings before exposure. |


```sh
python scripts/capture_walkthrough.py
```

The script requires the existing application environment and `ffmpeg`. It
creates all frames in a temporary directory and removes them automatically.
