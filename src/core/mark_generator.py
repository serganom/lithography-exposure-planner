import math

from models.mark import AlignmentMark


class MarkGenerator:
    def __init__(self, field_size_mm: float = 0.6):
        self.field_size_mm = field_size_mm

    def generate_grid(
        self,
        mark_type: str = "R23",
        step_x: float = 2.0,
        step_y: float = 2.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        total_width: float = 10.0,
        total_height: float = 10.0,
        arm_length: float = 20.0,
        arm_width: float = 2.0,
        layer_group: str = "gate",
    ) -> list[AlignmentMark]:
        marks = []
        counter = 0
        y = offset_y
        while y <= total_height:
            x = offset_x
            while x <= total_width:
                counter += 1
                marks.append(AlignmentMark(
                    mark_id=f"{mark_type}_{counter}",
                    mark_type=mark_type,
                    center_x=x,
                    center_y=y,
                    arm_length=arm_length,
                    arm_width=arm_width,
                    layer_group=layer_group,
                ))
                x += step_x
            y += step_y
        return marks

    def distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    def find_nearest_mark(
        self, field_x: float, field_y: float, marks: list[AlignmentMark]
    ) -> tuple[AlignmentMark | None, float]:
        nearest = None
        min_dist = float("inf")
        for m in marks:
            d = self.distance(field_x, field_y, m.center_x, m.center_y)
            if d < min_dist:
                min_dist = d
                nearest = m
        return nearest, min_dist
