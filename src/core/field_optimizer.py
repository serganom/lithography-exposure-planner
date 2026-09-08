import math

from core.mark_generator import MarkGenerator
from models.field import ExposureField
from models.mark import AlignmentMark


class FieldOptimizer:
    @staticmethod
    def sort_snake(fields: list[ExposureField]) -> list[ExposureField]:
        sorted_fields = sorted(fields, key=lambda f: (-f.center_y, f.center_x))
        groups = []
        current_y = None
        current_group = []
        for f in sorted_fields:
            if current_y is None or abs(f.center_y - current_y) > 1e-6:
                if current_group:
                    groups.append(current_group)
                current_group = [f]
                current_y = f.center_y
            else:
                current_group.append(f)
        if current_group:
            groups.append(current_group)
        result = []
        for idx, group in enumerate(groups):
            if idx % 2 == 0:
                result.extend(sorted(group, key=lambda f: f.center_x))
            else:
                result.extend(sorted(group, key=lambda f: -f.center_x))
        for i, f in enumerate(result):
            f.index = i
        return result

    @staticmethod
    def sort_raster(fields: list[ExposureField]) -> list[ExposureField]:
        result = sorted(fields, key=lambda f: (-f.center_y, f.center_x))
        for i, f in enumerate(result):
            f.index = i
        return result

    @staticmethod
    def sort_spiral(fields: list[ExposureField]) -> list[ExposureField]:
        if not fields:
            return []
        cx = sum(f.center_x for f in fields) / len(fields)
        cy = sum(f.center_y for f in fields) / len(fields)
        def angle_key(f):
            return math.atan2(f.center_y - cy, f.center_x - cx)
        def dist_key(f):
            return (f.center_x - cx) ** 2 + (f.center_y - cy) ** 2
        by_angle = sorted(fields, key=angle_key)
        by_dist = sorted(fields, key=dist_key)
        result = []
        used = set()
        for f in by_dist:
            if f.name not in used:
                result.append(f)
                used.add(f.name)
        for f in by_angle:
            if f.name not in used:
                result.append(f)
                used.add(f.name)
        for i, f in enumerate(result):
            f.index = i
        return result

    @staticmethod
    def assign_nearest_marks(fields: list[ExposureField], marks: list[AlignmentMark]):
        gen = MarkGenerator()
        for f in fields:
            nearest, dist = gen.find_nearest_mark(f.center_x, f.center_y, marks)
            if nearest:
                f.mark_id = nearest.mark_id
                f.mark_distance = round(dist, 5)
