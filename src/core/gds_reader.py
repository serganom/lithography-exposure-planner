import logging
import math
from pathlib import Path
from typing import Optional

import gdspy
import numpy as np

from models.layer import LayerInfo
from models.project import ModuleInfo


class GdsReader:
    def __init__(self):
        self.lib: Optional[gdspy.GdsLibrary] = None
        self.filepath: str = ""
        self._version: str = ""

    def load(self, filepath: str) -> bool:
        filepath = str(Path(filepath).resolve())
        try:
            self.lib = gdspy.GdsLibrary()
            self.lib.read_gds(filepath, units="convert")
            self.filepath = filepath
            name = Path(filepath).stem
            self._version = name
            for prefix in ["!map_eval_GaN_V", "!map_eval_GaN_v"]:
                if prefix in name:
                    self._version = name.split(prefix)[-1]
                    break
            return True
        except Exception as e:
            self.lib = None
            self.filepath = ""
            logging.getLogger(__name__).exception("Error loading GDS %s: %s", filepath, e)
            return False

    @property
    def version(self) -> str:
        return self._version

    def get_top_cell(self) -> Optional[gdspy.Cell]:
        if self.lib is None:
            return None
        top_name = f"!map_eval_GaN_V{self._version}"
        if top_name in self.lib.cells:
            return self.lib.cells[top_name]
        for c in self.lib.top_level():
            return c
        return None

    def _iter_polygon_specs(self, cell):
        """Yield (layer, datatype, vertices) for direct cell polygons."""
        if hasattr(cell, 'elements'):
            for element in cell.elements:
                if isinstance(element, gdspy.Polygon):
                    try:
                        yield int(element.layer), int(element.datatype), element.points
                    except (IndexError, TypeError, ValueError):
                        continue
                elif isinstance(element, gdspy.PolygonSet):
                    for i in range(len(element.layers)):
                        try:
                            yield (
                                int(element.layers[i]),
                                int(element.datatypes[i]),
                                element.polygons[i],
                            )
                        except (IndexError, TypeError, ValueError):
                            continue
        elif hasattr(cell, 'polygons'):
            for poly in cell.polygons:
                for i in range(len(poly.layers)):
                    try:
                        yield int(poly.layers[i]), int(poly.datatypes[i]), poly.polygons[i]
                    except (IndexError, TypeError, ValueError):
                        continue

    def _iter_polygons(self, cell):
        """Yield (layer, vertices) pairs from a cell (works in gdspy 1.4.x–1.6.x)."""
        if hasattr(cell, 'elements'):
            for element in cell.elements:
                if isinstance(element, gdspy.Polygon):
                    try:
                        yield int(element.layer), element.points
                    except (IndexError, TypeError, ValueError):
                        continue
                elif isinstance(element, gdspy.PolygonSet):
                    for i in range(len(element.layers)):
                        try:
                            yield int(element.layers[i]), element.polygons[i]
                        except (IndexError, TypeError, ValueError):
                            continue
        elif hasattr(cell, 'polygons'):
            for poly in cell.polygons:
                for i in range(len(poly.layers)):
                    try:
                        yield int(poly.layers[i]), poly.polygons[i]
                    except (IndexError, TypeError, ValueError):
                        continue

    def get_layer_list(self) -> list[int]:
        return sorted({layer for layer, _datatype in self.get_layer_specs()})

    def get_layer_info(self, layer_numbers: list[int] = None) -> dict[int, LayerInfo]:
        if self.lib is None:
            return {}
        if layer_numbers is None:
            layer_numbers = self.get_layer_list()

        result = {ln: LayerInfo(number=ln) for ln in layer_numbers}
        areas = self._compute_layer_areas(layer_numbers)
        for ln, area in areas.items():
            if ln in result:
                result[ln].has_data = area > 0
                result[ln].polygon_area = area
        return result
    def get_layer_specs(self) -> list[tuple[int, int]]:
        """Return the exact GDS (layer, datatype) combinations in the file."""
        if self.lib is None:
            return []
        specs = set()
        for cell in self.lib.cells.values():
            for layer, datatype, _vertices in self._iter_polygon_specs(cell):
                specs.add((layer, datatype))
        return sorted(specs)


    def _polygon_area(self, verts) -> float:
        """Shoelace formula — returns area in input units squared (µm²)."""
        x = verts[:, 0]
        y = verts[:, 1]
        return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))

    def _compute_layer_areas(self, layer_numbers: list[int]) -> dict[int, float]:
        areas = {ln: 0.0 for ln in layer_numbers}
        target = set(layer_numbers)
        for cell in self.lib.cells.values():
            for ln, verts in self._iter_polygons(cell):
                if ln in target:
                    areas[ln] += self._polygon_area(verts)
        # Convert µm² → mm²
        for ln in areas:
            areas[ln] /= 1_000_000.0
        return areas

    def get_top_level_modules(self) -> list[str]:
        top = self.get_top_cell()
        if top is None:
            return []
        seen = set()
        modules = []
        for inst in top.references:
            name = inst.ref_cell.name
            if name not in seen:
                seen.add(name)
                modules.append(name)
        return sorted(modules)

    def get_module_layers(self, module_name: str) -> set[int]:
        if self.lib is None or module_name not in self.lib.cells:
            return set()
        layers = set()
        visited = set()

        def walk(cname):
            if cname in visited:
                return
            visited.add(cname)
            cell = self.lib.cells[cname]
            for ln, _ in self._iter_polygons(cell):
                layers.add(ln)
            for inst in cell.references:
                if inst.ref_cell.name in self.lib.cells:
                    walk(inst.ref_cell.name)

        walk(module_name)
        return layers

    def analyze_modules(self, gate_layers: list[int], cap_layers: list[int]) -> list[ModuleInfo]:
        gate_set = set(gate_layers)
        cap_set = set(cap_layers)
        modules = []
        for mname in self.get_top_level_modules():
            mlayers = self.get_module_layers(mname)
            has_gate = bool(mlayers & gate_set)
            has_cap = bool(mlayers & cap_set)
            if has_gate or has_cap:
                modules.append(ModuleInfo(
                    name=mname,
                    has_gate=has_gate,
                    has_cap=has_cap,
                    layer_numbers=sorted(mlayers),
                ))
        return modules

    def _bbox_max_dim(self, verts: np.ndarray) -> float:
        """Maximum bounding-box dimension in µm."""
        mn = verts.min(axis=0)
        mx = verts.max(axis=0)
        return max(float(mx[0] - mn[0]), float(mx[1] - mn[1]))

    def _polygon_center(self, verts: np.ndarray) -> tuple[float, float]:
        """Bounding-box center → (x, y) in µm."""
        c = (verts.min(axis=0) + verts.max(axis=0)) / 2.0
        return float(c[0]), float(c[1])

    @staticmethod
    def _clean_polygon_vertices(verts: np.ndarray) -> np.ndarray:
        points = np.asarray(verts, dtype=float)
        if len(points) > 1 and np.allclose(points[0], points[-1]):
            points = points[:-1]
        return points

    def _is_cross_polygon(self, verts: np.ndarray) -> bool:
        """Recognize one-piece, centrally symmetric cross polygons.

        A conventional plus mark has 12 vertices: eight convex corners and
        four concave corners. The checks are rotation-independent, so marks
        inside rotated or reflected GDS references are also recognized.
        """
        points = self._clean_polygon_vertices(verts)
        if len(points) != 12 or not np.isfinite(points).all():
            return False

        span = points.max(axis=0) - points.min(axis=0)
        scale = float(max(span))
        if scale <= 0 or float(min(span)) <= 0:
            return False

        center = points.mean(axis=0)
        relative = points - center
        tolerance = max(scale * 1e-6, 1e-9)
        for point in relative:
            if np.min(np.linalg.norm(relative + point, axis=1)) > tolerance:
                return False

        edges = np.roll(points, -1, axis=0) - points
        next_edges = np.roll(edges, -1, axis=0)
        turns = edges[:, 0] * next_edges[:, 1] - edges[:, 1] * next_edges[:, 0]
        significant = turns[np.abs(turns) > tolerance * tolerance]
        if len(significant) != 12:
            return False
        positive = int(np.count_nonzero(significant > 0))
        negative = int(np.count_nonzero(significant < 0))
        if min(positive, negative) != 4:
            return False

        bbox_area = float(span[0] * span[1])
        fill_ratio = self._polygon_area(points) / bbox_area
        return 0.05 <= fill_ratio <= 0.8

    def _rectangle_properties(self, verts: np.ndarray):
        """Return center, long-axis direction, length and width for a rectangle."""
        points = self._clean_polygon_vertices(verts)
        if len(points) != 4 or not np.isfinite(points).all():
            return None
        edges = np.roll(points, -1, axis=0) - points
        lengths = np.linalg.norm(edges, axis=1)
        if np.min(lengths) <= 0:
            return None
        longest = int(np.argmax(lengths))
        length = float(lengths[longest])
        width = float(np.min(lengths))
        if length / width < 1.5:
            return None
        unit_axis = edges[longest] / length
        return points.mean(axis=0), unit_axis, length, width

    @staticmethod
    def _deduplicate_points(
        points: list[tuple[float, float]], tolerance_um: float = 1e-6
    ) -> list[tuple[float, float]]:
        unique = []
        for point in points:
            candidate = np.asarray(point, dtype=float)
            if any(
                np.linalg.norm(candidate - np.asarray(existing, dtype=float)) <= tolerance_um
                for existing in unique
            ):
                continue
            unique.append((float(candidate[0]), float(candidate[1])))
        return unique

    def _extract_cross_centers(
        self, cell, layer: int, datatype: int | None
    ) -> list[tuple[float, float]]:
        """Find one-piece crosses and crosses made from two rectangles."""
        cross_centers: list[tuple[float, float]] = []
        rectangles = []
        for spec, polygons in cell.get_polygons(by_spec=True).items():
            polygon_layer = int(spec[0]) if isinstance(spec, tuple) else int(spec)
            polygon_datatype = int(spec[1]) if isinstance(spec, tuple) else 0
            if polygon_layer != layer:
                continue
            if datatype is not None and polygon_datatype != datatype:
                continue
            for vertices in polygons:
                points = np.asarray(vertices, dtype=float)
                if self._is_cross_polygon(points):
                    cross_centers.append(self._polygon_center(points))
                    continue
                rectangle = self._rectangle_properties(points)
                if rectangle is not None:
                    rectangles.append(rectangle)

        paired = set()
        for first in range(len(rectangles)):
            if first in paired:
                continue
            center_a, axis_a, _length_a, width_a = rectangles[first]
            for second in range(first + 1, len(rectangles)):
                if second in paired:
                    continue
                center_b, axis_b, _length_b, width_b = rectangles[second]
                center_tolerance = max(min(width_a, width_b) * 0.1, 1e-6)
                if np.linalg.norm(center_a - center_b) > center_tolerance:
                    continue
                if abs(float(np.dot(axis_a, axis_b))) > 0.1:
                    continue
                center = (center_a + center_b) / 2.0
                cross_centers.append((float(center[0]), float(center[1])))
                paired.update((first, second))
                break

        return self._deduplicate_points(cross_centers)

    def _sref_transform(self, verts: np.ndarray,
                         origin: tuple[float, float],
                         rotation_deg: float, mag: float,
                         x_reflection: bool = False) -> np.ndarray:
        """Apply a gdspy SREF transform to vertices (rotation is stored in degrees)."""
        if mag != 1.0:
            verts = verts * mag
        if x_reflection:
            verts = verts * np.array([1.0, -1.0])
        if rotation_deg:
            rotation_rad = math.radians(rotation_deg)
            c, s = math.cos(rotation_rad), math.sin(rotation_rad)
            rot = np.array([[c, -s], [s, c]])
            verts = verts @ rot.T
        return verts + np.array(origin)

    def _find_mark_cells(
        self, target_layer: int, max_size_um: float = 10.0, datatype: int | None = None
    ):
        """Return cells likely to contain alignment marks.

        Criteria (any match):
          1. cell name contains ``mark`` (case‑insensitive)
          2. ≥50 DIRECT polygons on *target_layer* with bbox ≤ *max_size_um*
        """
        found = []
        for cell in self.lib.cells.values():
            if "mark" in cell.name.lower():
                found.append(cell)
                continue
            count = small = 0
            for ln, polygon_datatype, verts in self._iter_polygon_specs(cell):
                if ln != target_layer:
                    continue
                if datatype is not None and polygon_datatype != datatype:
                    continue
                count += 1
                if self._bbox_max_dim(verts) <= max_size_um:
                    small += 1
            if count >= 50 and small >= count * 0.8:
                found.append(cell)
        return found

    def _cluster_centers(self, points_um: list[tuple[float, float]],
                         radius_um: float) -> list[tuple[float, float]]:
        """Group 2D points by proximity. Returns cluster centroids in µm."""
        if len(points_um) <= 1:
            return list(points_um)
        pts = np.array(points_um)
        n = len(pts)
        assigned = [False] * n
        clusters = []
        for i in range(n):
            if assigned[i]:
                continue
            indices = [i]
            assigned[i] = True
            changed = True
            while changed:
                changed = False
                centroid = pts[indices].mean(axis=0)
                for j in range(n):
                    if assigned[j]:
                        continue
                    if np.linalg.norm(pts[j] - centroid) <= radius_um:
                        indices.append(j)
                        assigned[j] = True
                        changed = True
            centroid = pts[indices].mean(axis=0)
            clusters.append((float(centroid[0]), float(centroid[1])))
        return clusters

    def _extract_mark_centers(self, cell, layer: int,
                               max_size_um: float,
                               cluster_radius_um: float,
                               datatype: int | None = None) -> list[tuple[float, float]]:
        """Extract polygon centers from *cell* on *layer*, then cluster by proximity.

        Returns list of (x, y) cluster centroids in µm (local cell coordinates).
        """
        points = []
        for ln, polygon_datatype, verts in self._iter_polygon_specs(cell):
            if ln != layer:
                continue
            if datatype is not None and polygon_datatype != datatype:
                continue
            if self._bbox_max_dim(verts) > max_size_um:
                continue
            points.append(self._polygon_center(verts))
        if not points:
            return []
        return self._cluster_centers(points, cluster_radius_um)

    def get_layer_polygons(
        self, layer: int, datatype: int | None = None
    ) -> list[np.ndarray]:
        """Get polygons on a layer/datatype at global coordinates, in mm."""
        top = self.get_top_cell()
        if top is None:
            return []
        try:
            raw = top.get_polygons(by_spec=True)
            result = []
            for spec, poly_list in raw.items():
                ln = int(spec[0]) if isinstance(spec, tuple) else int(spec)
                polygon_datatype = int(spec[1]) if isinstance(spec, tuple) else 0
                if ln != layer:
                    continue
                if datatype is not None and polygon_datatype != datatype:
                    continue
                for verts in poly_list:
                    result.append(np.array(verts, dtype=float) / 1000.0)
            return result
        except Exception:
            return []

    def extract_polygon_centers(self, layer: int,
                                 max_size_um: float = 10.0,
                                 cluster_radius_um: float = 30.0, *,
                                 datatype: int | None = None) -> list[tuple[float, float]]:
        """Find mark centers in the selected top cell's global coordinates.

        Cluster direct polygons in candidate mark cells, then follow every
        reachable SREF/AREF through the hierarchy. Unreferenced library cells
        never contribute local coordinates to the result. If no reachable
        candidate contains marks, use the flattened top-cell geometry.
        """
        if self.lib is None:
            return []
        top = self.get_top_cell()
        if top is None:

            return []
        try:
            cross_centers = self._extract_cross_centers(top, layer, datatype)
        except RecursionError as error:
            raise ValueError("Cyclic reference in GDS.") from error
        if cross_centers:
            return sorted(
                ((float(x) / 1000.0, float(y) / 1000.0) for x, y in cross_centers),
                key=lambda point: (point[1], point[0]),
            )

        local_centers = {
            cell.name: self._extract_mark_centers(
                cell, layer, max_size_um, cluster_radius_um, datatype
            )
            for cell in self._find_mark_cells(layer, max_size_um, datatype)
        }
        cache: dict[str, list[tuple[float, float]]] = {}

        def collect(cell, ancestors: set[str]) -> list[tuple[float, float]]:
            if cell.name in ancestors:
                raise ValueError(f"Cyclic reference in GDS cell: {cell.name}.")
            if cell.name in cache:
                return cache[cell.name]

            centers = list(local_centers.get(cell.name, []))
            path = ancestors | {cell.name}
            for reference in cell.references:
                if not isinstance(reference, (gdspy.CellReference, gdspy.CellArray)):
                    raise ValueError(f"Unsupported reference in GDS cell {cell.name}.")
                child = reference.ref_cell
                if isinstance(child, str):
                    child = self.lib.cells.get(child)
                if child is None:
                    raise ValueError(f"Child cell was not found for {cell.name}.")
                child_centers = collect(child, path)
                if not child_centers:
                    continue
                points = np.asarray(child_centers, dtype=float)
                origin = reference.origin if reference.origin is not None else (0.0, 0.0)
                rotation = float(reference.rotation or 0.0)
                mag = (
                    float(reference.magnification)
                    if reference.magnification is not None else 1.0
                )
                reflected = bool(reference.x_reflection)

                if isinstance(reference, gdspy.CellArray):
                    # gdspy applies magnification to cell coordinates, not spacing.
                    # Array offsets are then reflected/rotated with the instance.
                    for column in range(reference.columns):
                        for row in range(reference.rows):
                            offset = np.array([
                                column * reference.spacing[0],
                                row * reference.spacing[1],
                            ])
                            transformed = self._sref_transform(
                                points * mag + offset, origin, rotation, 1.0, reflected
                            )
                            centers.extend((float(x), float(y)) for x, y in transformed)
                else:
                    transformed = self._sref_transform(
                        points, origin, rotation, mag, reflected
                    )
                    centers.extend((float(x), float(y)) for x, y in transformed)
            cache[cell.name] = centers
            return centers

        centers_um = collect(top, set())
        if not centers_um:
            # The library may contain unused mark cells: only the selected
            # top cell's reachable geometry is a valid fallback.
            points = []
            for spec, polygons in top.get_polygons(by_spec=True).items():
                polygon_layer = int(spec[0]) if isinstance(spec, tuple) else int(spec)
                polygon_datatype = int(spec[1]) if isinstance(spec, tuple) else 0
                if polygon_layer != layer:
                    continue
                if datatype is not None and polygon_datatype != datatype:
                    continue
                for vertices in polygons:
                    if self._bbox_max_dim(vertices) <= max_size_um:
                        points.append(self._polygon_center(vertices))
            centers_um = self._cluster_centers(points, cluster_radius_um)

        return [(float(x) / 1000.0, float(y) / 1000.0) for x, y in centers_um]

    def extract_module_gds(self, module_name: str, output_path: str) -> bool:
        if self.lib is None or module_name not in self.lib.cells:
            return False
        import os
        lib = gdspy.GdsLibrary()
        lib.read_gds(self.filepath, units="import")

        referenced = set()
        def collect(cname):
            if cname in referenced:
                return
            referenced.add(cname)
            cell = lib.cells[cname]
            for inst in cell.references:
                collect(inst.ref_cell.name)

        collect(module_name)
        for cname in list(lib.cells.keys()):
            if cname not in referenced and cname != module_name:
                del lib.cells[cname]
        for cname in list(lib.cells.keys()):
            cell = lib.cells[cname]
            cell.references = [inst for inst in cell.references if inst.ref_cell.name in lib.cells]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        lib.write_gds(output_path)
        return True
