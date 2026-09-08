import math
import re
from pathlib import Path

from models.con_file import ConFileData
from models.field import ExposureField
from models.mark import AlignmentMark
from utils.file_io import atomic_write_text


class ConParser:
    """Read the supported CON subset and fail closed when regeneration is unsafe."""

    NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    RE_CZ = re.compile(rf"CZ({NUMBER})\s*,\s*(\d+)\s*;")
    RE_MARK_R23 = re.compile(rf"R23\s+({NUMBER})\s*,\s*({NUMBER})\s*;")
    RE_MARK_R2 = re.compile(
        rf"R2\s+({NUMBER})\s*,\s*({NUMBER})\s*;\s*({NUMBER})\s*,\s*({NUMBER})\s*;"
    )
    RE_PC = re.compile(r"PC([^\s;]+)\s*;")
    RE_PP = re.compile(r"PP([^\s;]+)\s*;")
    RE_COORDS = re.compile(rf"({NUMBER})\s*,\s*({NUMBER})\s*;")
    RE_DOSE = re.compile(rf"LayoutBEAMER:DOSE_RESOLUTION\s*=\s*({NUMBER})")
    RE_COMMENT_MODULE = re.compile(r"/\*---\s*([^\s]+)\.CON\s*---\*/")

    @staticmethod
    def _command_lines(text: str) -> list[str]:
        # Keep line positions while preventing comments from becoming commands.
        text = re.sub(
            r"/\*.*?\*/",
            lambda match: re.sub(r"[^\n]", " ", match.group()),
            text,
            flags=re.DOTALL,
        )
        return text.splitlines()

    def parse(self, filepath: str | Path) -> ConFileData:
        path = Path(filepath).resolve()
        return self.parse_text(path.read_text(encoding="utf-8-sig"), str(path))

    def parse_text(self, text: str, filepath: str = "") -> ConFileData:
        con = ConFileData()
        con.filepath = str(Path(filepath).resolve()) if filepath else ""
        con.module_name = Path(filepath).stem if filepath else "job"
        con.raw_lines = text.splitlines(keepends=True)
        lines = self._command_lines(text)
        current_mark = None
        counters = {"R2": 0, "R23": 0}

        for index, command in enumerate(lines):
            raw_line = con.raw_lines[index] if index < len(con.raw_lines) else ""
            module = self.RE_COMMENT_MODULE.search(raw_line)
            if module:
                con.module_name = module.group(1)
            dose = self.RE_DOSE.search(raw_line)
            if dose:
                con.dose_resolution = float(dose.group(1))

            line = command.strip()
            field_size = self.RE_CZ.fullmatch(line)
            if field_size:
                con.field_size = float(field_size.group(1))
                con.resolution = int(field_size.group(2))
                continue

            r2 = self.RE_MARK_R2.fullmatch(line)
            r23 = self.RE_MARK_R23.fullmatch(line)
            if r2 or r23:
                match = r2 or r23
                mark_type = "R2" if r2 else "R23"
                counters[mark_type] += 1
                current_mark = AlignmentMark(
                    mark_id=f"{mark_type}_{counters[mark_type]}",
                    mark_type=mark_type,
                    center_x=float(match.group(1)),
                    center_y=float(match.group(2)),
                    corner2_x=float(match.group(3)) if r2 else None,
                    corner2_y=float(match.group(4)) if r2 else None,
                )
                con.marks.append(current_mark)
                continue

            field = self.RE_PC.fullmatch(line)
            if field:
                coords = self._find_coords(lines, index + 1)
                if coords is None:
                    raise ValueError(f"Coordinates are missing after PC{field.group(1)}.")
                con.fields.append(
                    ExposureField(
                        name=field.group(1),
                        index=len(con.fields),
                        center_x=coords[0],
                        center_y=coords[1],
                        mark_id=current_mark.mark_id if current_mark else None,
                    )
                )
        return con

    def _find_coords(self, lines: list[str], start: int):
        for line in lines[start:]:
            if not line.strip():
                continue
            match = self.RE_COORDS.fullmatch(line.strip())
            return (float(match.group(1)), float(match.group(2))) if match else None
        return None

    def _validate_source(self, con: ConFileData) -> None:
        if not con.raw_lines:
            return
        text = "".join(con.raw_lines)
        tokens = [line.strip() for line in self._command_lines(text) if line.strip()]
        index = 0
        while index < len(tokens):
            line = tokens[index]
            if (
                self.RE_CZ.fullmatch(line)
                or self.RE_MARK_R2.fullmatch(line)
                or self.RE_MARK_R23.fullmatch(line)
                or line == "!END"
            ):
                index += 1
                continue
            field = self.RE_PC.fullmatch(line)
            if field and index + 3 < len(tokens):
                first = self.RE_COORDS.fullmatch(tokens[index + 1])
                pp = self.RE_PP.fullmatch(tokens[index + 2])
                second = self.RE_COORDS.fullmatch(tokens[index + 3])
                if first and pp and second and pp.group(1) == field.group(1):
                    first_coords = tuple(float(value) for value in first.groups())
                    second_coords = tuple(float(value) for value in second.groups())
                    if first_coords != second_coords:
                        raise ValueError(
                            f"Field {field.group(1)} has different PC and PP coordinates. "
                            "Automatic rewriting of this CON file is not supported."
                        )
                    index += 4
                    continue
            raise ValueError(
                f"Automatic rewriting does not support this CON command: {line[:100]}. "
                "The source text was preserved; review the format manually."
            )

        source = self.parse_text(text)
        referenced = {field.mark_id for field in source.fields}
        if any(mark.mark_id not in referenced for mark in source.marks):
            raise ValueError(
                "The source CON contains mark commands without an associated field "
                "such as a separate global-alignment command. "
                "Automatic rewriting of this file is blocked."
            )

    def serialize(self, con: ConFileData) -> str:
        self._validate_source(con)
        if not math.isfinite(con.field_size) or con.field_size <= 0 or con.resolution <= 0:
            raise ValueError("CON field size and resolution must be positive.")
        if not math.isfinite(con.dose_resolution) or con.dose_resolution <= 0:
            raise ValueError("DOSE_RESOLUTION must be positive.")
        if "\n" in con.module_name or "\r" in con.module_name or "*/" in con.module_name:
            raise ValueError("Invalid module name.")

        marks = {mark.mark_id: mark for mark in con.marks}
        if len(marks) != len(con.marks):
            raise ValueError("Duplicate mark identifiers were found.")

        lines = [
            f"/*--- {con.module_name}.CON ---*/",
            f"/* LayoutBEAMER:DOSE_RESOLUTION = {con.dose_resolution} */",
            f"CZ{con.field_size:.3f},{con.resolution};",
        ]
        active_mark = None
        field_names = set()
        for field in con.fields:
            if not re.fullmatch(r"[^\s;]+", field.name) or field.name in field_names:
                raise ValueError(f"Invalid or duplicate field name: {field.name}.")
            if not all(math.isfinite(value) for value in (field.center_x, field.center_y)):
                raise ValueError(f"Invalid coordinates for field {field.name}.")
            field_names.add(field.name)
            mark_id = field.mark_id or None
            if mark_id is None and active_mark is not None:
                raise ValueError(
                    f"Field {field.name} has no mark after a field with an assigned mark. "
                    "Resetting an active mark is not implemented; assign a mark explicitly."
                )
            if mark_id and mark_id != active_mark:
                mark = marks.get(mark_id)
                if mark is None:
                    raise ValueError(f"Mark {mark_id} assigned to field {field.name} was not found.")
                if not all(math.isfinite(value) for value in (mark.center_x, mark.center_y)):
                    raise ValueError(f"Invalid coordinates for mark {mark_id}.")
                if mark.is_r2:
                    if (
                        mark.corner2_x is None
                        or mark.corner2_y is None
                        or not math.isfinite(mark.corner2_x)
                        or not math.isfinite(mark.corner2_y)
                    ):
                        raise ValueError(f"Mark {mark_id} requires two coordinate pairs.")
                    lines.append(
                        f"R2 {mark.center_x:.3f}, {mark.center_y:.3f}; "
                        f"{mark.corner2_x:.3f}, {mark.corner2_y:.3f};"
                    )
                elif mark.mark_type == "R23":
                    lines.append(f"R23 {mark.center_x:.3f}, {mark.center_y:.3f};")
                else:
                    raise ValueError(f"Unsupported mark type: {mark.mark_type}.")
                active_mark = mark_id

            lines.extend(
                [
                    f"PC{field.name};",
                    f"{field.center_x:.5f},{field.center_y:.5f};",
                    f"PP{field.name};",
                    f"{field.center_x:.5f},{field.center_y:.5f};",
                ]
            )
        lines.append("!END")
        return "\n".join(lines) + "\n"

    def write(self, con: ConFileData, output_path: str | None = None):
        path = output_path or con.filepath
        if not path:
            raise ValueError("No output path was selected for the CON file.")
        atomic_write_text(path, self.serialize(con), create_backup=True)
