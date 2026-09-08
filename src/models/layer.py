from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LayerGroup(Enum):
    NONE = 0
    GATE = 1
    CAP = 2
    BOTH = 3

    @staticmethod
    def from_booleans(gate: bool, cap: bool) -> LayerGroup:
        if gate and cap:
            return LayerGroup.BOTH
        if gate:
            return LayerGroup.GATE
        if cap:
            return LayerGroup.CAP
        return LayerGroup.NONE


@dataclass
class LayerInfo:
    number: int
    has_data: bool = False
    gate_enabled: bool = False
    cap_enabled: bool = False
    polygon_area: float = 0.0

    @property
    def group(self) -> LayerGroup:
        return LayerGroup.from_booleans(self.gate_enabled, self.cap_enabled)


