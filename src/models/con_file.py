from dataclasses import dataclass, field

from .field import ExposureField
from .mark import AlignmentMark


@dataclass
class ConFileData:
    filepath: str = ""
    module_name: str = ""
    field_size: float = 0.600
    resolution: int = 60000
    dose_resolution: float = 0.001
    fields: list[ExposureField] = field(default_factory=list)
    marks: list[AlignmentMark] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)

    def find_mark_by_id(self, mark_id: str) -> AlignmentMark | None:
        for m in self.marks:
            if m.mark_id == mark_id:
                return m
        return None


@dataclass
class ConFileGroup:
    gate: ConFileData | None = None
    cap: ConFileData | None = None
