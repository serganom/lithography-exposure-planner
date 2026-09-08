from models.con_file import ConFileData
from models.project import ModuleInfo


def generate_report(
    version: str,
    modules: list[ModuleInfo],
    gate_layers: list[int],
    cap_layers: list[int],
    con_gate: ConFileData | None = None,
    con_cap: ConFileData | None = None,
) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"Lithography Exposure Report - V{version}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("--- Layer Configuration ---")
    lines.append(f"  Gate layers: {gate_layers}")
    lines.append(f"  Cap layers:  {cap_layers}")
    lines.append("")

    lines.append("--- Modules ---")
    for m in modules:
        labels = []
        if m.has_gate:
            labels.append("GATE")
        if m.has_cap:
            labels.append("CAP")
        lines.append(f"  {m.name} [{', '.join(labels)}]  layers={m.layer_numbers}")
    lines.append("")

    for group_name, con in [("Gate", con_gate), ("Cap", con_cap)]:
        if con is None:
            continue
        lines.append(f"--- {group_name} CON File: {con.module_name} ---")
        lines.append(f"  Field size: {con.field_size} mm")
        lines.append(f"  Resolution: {con.resolution} dots")
        lines.append(f"  Fields: {len(con.fields)}")
        lines.append(f"  Marks: {len(con.marks)}")
        lines.append("")
        lines.append("  Exposure order:")
        for f in con.fields:
            mark_info = f" -> mark {f.mark_id}" if f.mark_id else ""
            dist_info = f" (d={f.mark_distance}mm)" if f.mark_distance else ""
            lines.append(f"    {f.index:4d}. {f.name}  ({f.center_x:.5f}, {f.center_y:.5f}){mark_info}{dist_info}")
        lines.append("")

    return "\n".join(lines)
