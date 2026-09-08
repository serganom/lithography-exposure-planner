from __future__ import annotations

from dataclasses import dataclass, field

from .con_file import ConFileGroup


@dataclass
class Project:
    gds_file: str = ""
    version_name: str = ""
    output_dir: str = ""
    gate_layers: list[int] = field(default_factory=list)
    cap_layers: list[int] = field(default_factory=list)
    modules: list[ModuleInfo] = field(default_factory=list)
    con_files: ConFileGroup = field(default_factory=ConFileGroup)


@dataclass
class ModuleInfo:
    name: str
    has_gate: bool = False
    has_cap: bool = False
    layer_numbers: list[int] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "has_gate": self.has_gate,
            "has_cap": self.has_cap,
            "layers": self.layer_numbers,
        }

    @staticmethod
    def from_dict(d: dict) -> ModuleInfo:
        return ModuleInfo(
            name=d["name"],
            has_gate=d.get("has_gate", False),
            has_cap=d.get("has_cap", False),
            layer_numbers=d.get("layers", []),
        )
