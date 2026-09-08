from pathlib import Path

from core.gds_reader import GdsReader
from models.project import ModuleInfo
from utils.file_io import atomic_write_text


class ModuleExtractor:
    def __init__(self, gds_reader: GdsReader):
        self.reader = gds_reader

    def extract(self, modules: list[ModuleInfo], output_base: str,
                gate_layers: list[int], cap_layers: list[int],
                progress_callback=None) -> dict[str, bool]:
        base = Path(output_base)
        results = {}

        for i, mod in enumerate(modules):
            if progress_callback:
                progress_callback(i, len(modules), mod.name)

            mod_dir = base / mod.name
            mod_dir.mkdir(parents=True, exist_ok=True)

            if mod.has_gate:
                gate_dir = mod_dir / f"gate_{mod.name}"
                gate_dir.mkdir(parents=True, exist_ok=True)
                con_path = gate_dir / f"gate_{mod.name}.CON"
                if not con_path.exists():
                    self._write_initial_con(con_path, mod.name, "gate")

            if mod.has_cap:
                cap_dir = mod_dir / f"cap_{mod.name}"
                cap_dir.mkdir(parents=True, exist_ok=True)
                con_path = cap_dir / f"cap_{mod.name}.CON"
                if not con_path.exists():
                    self._write_initial_con(con_path, mod.name, "cap")

            gds_path = mod_dir / f"{mod.name}.gds"
            ok = self.reader.extract_module_gds(mod.name, str(gds_path))
            results[mod.name] = ok

        return results

    def _write_initial_con(self, path: Path, module_name: str, group: str):
        content = (
            f"/*--- {group}_{module_name}.CON ---*/\n"
            f"/* LayoutBEAMER:DOSE_RESOLUTION = 0.001 */\n"
            f"CZ0.600,60000;\n"
            f"!END\n"
        )
        atomic_write_text(path, content)
