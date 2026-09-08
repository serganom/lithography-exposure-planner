from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlignmentMark:
    mark_id: str
    mark_type: str = "R23"
    center_x: float = 0.0
    center_y: float = 0.0
    corner2_x: float | None = None
    corner2_y: float | None = None
    arm_length: float = 20.0
    arm_width: float = 2.0
    layer_group: str = "gate"

    @property
    def is_r2(self) -> bool:
        return self.mark_type == "R2"
