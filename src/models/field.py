from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExposureField:
    name: str
    index: int = 0
    center_x: float = 0.0
    center_y: float = 0.0
    mark_id: str | None = None
    mark_distance: float | None = None
