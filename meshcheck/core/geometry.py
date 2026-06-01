import bmesh
import bpy
from dataclasses import dataclass, field

from mathutils import Vector
from mathutils.geometry import tessellate_polygon

from ...mesh_metrics import get_evaluated_object_triangle_count
from .config import (
    _get_check_settings_signature,
    _resolve_enabled_ids,
    get_double_epsilon,
    get_long_tri_degenerate_epsilon,
    get_long_tri_ratio_threshold,
    get_missing_sharp_angle_radians,
    get_missing_sharp_skip_marked,
    get_pole_threshold,
    get_tiny_face_area_threshold,
)


OBJECT_MEMOS = {}
MIN_DOUBLE_EPSILON = 1e-9


def _get_mesh_object_state_signature(obj):
    if obj is None or getattr(obj, "data", None) is None:
        return ()

    mesh = obj.data
    try:
        vert_count = len(getattr(mesh, "vertices", ()))
        edge_count = len(getattr(mesh, "edges", ()))
        poly_count = len(getattr(mesh, "polygons", ()))
    except Exception:
        vert_count = 0
        edge_count = 0
        poly_count = 0

    return (
        int(obj.as_pointer()),
        int(mesh.as_pointer()),
        getattr(obj, "mode", ""),
        bool(getattr(mesh, "is_editmode", False)),
        vert_count,
        edge_count,
        poly_count,
    )


def _get_evaluated_triangle_signature(obj, depsgraph=None):
    if obj is None:
        return 0
    try:
        return int(get_evaluated_object_triangle_count(obj, depsgraph))
    except Exception:
        return 0


def _get_preview_metadata_signature(obj):
    mesh = getattr(obj, "data", None) if obj is not None else None
    if mesh is None:
        return ((), 0)

    try:
        material_signature = tuple(
            int(material.as_pointer())
            for material in getattr(mesh, "materials", ())
            if material is not None
        )
    except Exception:
        material_signature = ()

    try:
        uv_count = len(getattr(mesh, "uv_layers", ()))
    except Exception:
        uv_count = 0

    return material_signature, uv_count


def _get_preview_object_state_signature(obj, depsgraph=None):
    return (
        _get_mesh_object_state_signature(obj)
        + (_get_evaluated_triangle_signature(obj, depsgraph),)
        + _get_preview_metadata_signature(obj)
    )


def _ensure_lookup_tables(bm):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return bm


def _build_bmesh(obj, depsgraph):
    del depsgraph
    if obj is None or getattr(obj, "data", None) is None:
        return None

    if getattr(obj.data, "is_editmode", False):
        try:
            return _ensure_lookup_tables(bmesh.from_edit_mesh(obj.data).copy())
        except (AttributeError, ReferenceError, RuntimeError, ValueError):
            return None

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return _ensure_lookup_tables(bm)
    except (AttributeError, ReferenceError, RuntimeError, ValueError):
        bm.free()
        return None


def _get_edit_bmesh(obj):
    if obj is None or getattr(obj, "data", None) is None or not getattr(obj.data, "is_editmode", False):
        return None
    try:
        return _ensure_lookup_tables(bmesh.from_edit_mesh(obj.data))
    except (AttributeError, ReferenceError, RuntimeError, ValueError):
        return None


def _safe_triangles(coords):
    if len(coords) < 3:
        return []
    try:
        triangles = tessellate_polygon([coords])
        if triangles:
            return [tuple(tri) for tri in triangles]
    except Exception:
        pass
    return [(0, idx, idx + 1) for idx in range(1, len(coords) - 1)]


def _point_payload(coord, normal):
    return (tuple(coord), tuple(normal))


def _segment_payload(start, end, start_normal, end_normal):
    return (
        tuple(start),
        tuple(end),
        tuple(start_normal),
        tuple(end_normal),
    )


def _get_edit_mesh_quick_signature(obj):
    bm = _get_edit_bmesh(obj)
    if bm is None:
        return ()
    return (
        len(bm.verts),
        len(bm.edges),
        len(bm.faces),
    )


def _triangle_long_ratio(a, b, c, zero_face_epsilon):
    edge_lengths = (
        (b - a).length,
        (c - b).length,
        (a - c).length,
    )
    longest_edge = max(edge_lengths)
    area2 = (b - a).cross(c - a).length
    if area2 <= zero_face_epsilon:
        return float("inf")
    denominator = zero_face_epsilon if zero_face_epsilon > 0.0 else 1e-30
    shortest_altitude = area2 / max(longest_edge, denominator)
    if shortest_altitude <= zero_face_epsilon:
        return float("inf")
    return longest_edge / shortest_altitude


@dataclass
class CheckGeometryMemo:
    object_name: str = ""
    mesh_key: int = 0
    mode_tag: str = ""
    enabled_ids: frozenset = field(default_factory=frozenset)
    detailed: bool = True
    state_signature: tuple = field(default_factory=tuple)
    settings_signature: tuple = field(default_factory=tuple)
    tris: int = 0
    non_manifold_segments: list = field(default_factory=list)
    ngon_faces: list = field(default_factory=list)
    double_points: list = field(default_factory=list)
    long_tri_segments: list = field(default_factory=list)
    long_tri_faces: list = field(default_factory=list)
    tiny_face_points: list = field(default_factory=list)
    tiny_face_faces: list = field(default_factory=list)
    pole_points: list = field(default_factory=list)
    isolated_points: list = field(default_factory=list)
    missing_sharp_segments: list = field(default_factory=list)
    non_manifold_count: int = 0
    ngon_count: int = 0
    double_vert_count: int = 0
    long_tri_count: int = 0
    tiny_face_count: int = 0
    pole_count: int = 0
    isolated_vert_count: int = 0
    missing_sharp_edge_count: int = 0

    @classmethod
    def from_object(cls, obj, depsgraph, enabled_ids=None, detailed=True, settings_signature=None):
        memo = cls()
        memo.refresh(
            obj,
            depsgraph,
            enabled_ids=enabled_ids,
            detailed=detailed,
            settings_signature=settings_signature,
        )
        return memo

    def refresh(self, obj, depsgraph, enabled_ids=None, detailed=True, settings_signature=None):
        self.object_name = obj.name
        self.mesh_key = int(obj.data.as_pointer()) if getattr(obj, "data", None) is not None else 0
        self.mode_tag = getattr(obj, "mode", "")
        self.enabled_ids = _resolve_enabled_ids(enabled_ids)
        self.detailed = bool(detailed)
        self.state_signature = _get_mesh_object_state_signature(obj)
        self.settings_signature = settings_signature or _get_check_settings_signature()
        self.tris = get_evaluated_object_triangle_count(obj, depsgraph)

        self.non_manifold_segments.clear()
        self.ngon_faces.clear()
        self.double_points.clear()
        self.long_tri_segments.clear()
        self.long_tri_faces.clear()
        self.tiny_face_points.clear()
        self.tiny_face_faces.clear()
        self.pole_points.clear()
        self.isolated_points.clear()
        self.missing_sharp_segments.clear()

        bm = _get_edit_bmesh(obj) if getattr(obj.data, "is_editmode", False) else _build_bmesh(obj, depsgraph)
        should_free_bm = bool(bm is not None and not getattr(obj.data, "is_editmode", False))
        try:
            if bm is None:
                return self

            self._capture_geometry(bm)
        finally:
            if should_free_bm:
                bm.free()

        return self

    def can_satisfy(self, enabled_ids=None, detailed=True):
        expected_ids = _resolve_enabled_ids(enabled_ids)
        if not expected_ids.issubset(self.enabled_ids):
            return False
        if detailed and not self.detailed:
            return False
        return True

    def is_stale(self, obj, enabled_ids=None, detailed=True, settings_signature=None):
        if obj is None or getattr(obj, "data", None) is None:
            return True
        if not self.can_satisfy(enabled_ids=enabled_ids, detailed=detailed):
            return True
        return (
            self.mesh_key != int(obj.data.as_pointer())
            or self.mode_tag != getattr(obj, "mode", "")
            or self.state_signature != _get_mesh_object_state_signature(obj)
            or self.settings_signature != (settings_signature or _get_check_settings_signature())
        )

    def _capture_geometry(self, bm):
        self._capture_faces(bm)
        self._capture_verts(bm)
        self._capture_edges(bm)

    def _capture_faces(self, bm):
        self.ngon_count = 0
        self.ngon_faces = []
        self.long_tri_count = 0
        self.long_tri_segments = []
        self.long_tri_faces = []
        self.tiny_face_count = 0
        self.tiny_face_points = []
        self.tiny_face_faces = []

        capture_ngons = "NGONS" in self.enabled_ids
        capture_long_tris = "LONG_TRIS" in self.enabled_ids
        capture_tiny_faces = "TINY_FACES" in self.enabled_ids
        if not (capture_ngons or capture_long_tris or capture_tiny_faces):
            return

        long_tri_threshold = get_long_tri_ratio_threshold(bpy.context) if capture_long_tris else None
        tiny_face_threshold = get_tiny_face_area_threshold(bpy.context) if capture_tiny_faces else None
        zero_face_epsilon = get_long_tri_degenerate_epsilon() if capture_long_tris else None

        for face in bm.faces:
            if capture_tiny_faces:
                area = face.calc_area()
                if area <= tiny_face_threshold:
                    self.tiny_face_count += 1
                    if self.detailed:
                        self.tiny_face_points.append(_point_payload(face.calc_center_median(), face.normal))
                        verts = [tuple(vert.co) for vert in face.verts]
                        self.tiny_face_faces.append(
                            {
                                "verts": verts,
                                "indices": _safe_triangles(verts),
                                "normal": tuple(face.normal),
                            }
                        )

            if capture_ngons and len(face.verts) > 4:
                self.ngon_count += 1
                if self.detailed:
                    verts = [tuple(vert.co) for vert in face.verts]
                    self.ngon_faces.append(
                        {
                            "verts": verts,
                            "indices": _safe_triangles(verts),
                            "normal": tuple(face.normal),
                        }
                    )

            if not capture_long_tris or len(face.verts) != 3:
                continue

            a = face.verts[0].co
            b = face.verts[1].co
            c = face.verts[2].co
            ratio = _triangle_long_ratio(a, b, c, zero_face_epsilon)
            if ratio < long_tri_threshold:
                continue

            self.long_tri_count += 1
            if not self.detailed:
                continue

            verts = [tuple(vert.co) for vert in face.verts]
            self.long_tri_faces.append(
                {
                    "verts": verts,
                    "indices": _safe_triangles(verts),
                    "normal": tuple(face.normal),
                }
            )

            self.long_tri_segments.extend(
                (
                    _segment_payload(a, b, face.normal, face.normal),
                    _segment_payload(b, c, face.normal, face.normal),
                    _segment_payload(c, a, face.normal, face.normal),
                )
            )

    def _capture_verts(self, bm):
        self.double_vert_count = 0
        self.double_points = []
        self.pole_count = 0
        self.pole_points = []
        self.isolated_vert_count = 0
        self.isolated_points = []

        capture_doubles = "DOUBLES" in self.enabled_ids
        capture_poles = "POLES" in self.enabled_ids
        capture_isolated = "ISOLATED_VERTS" in self.enabled_ids
        if not (capture_doubles or capture_poles or capture_isolated):
            return

        double_epsilon = max(get_double_epsilon(bpy.context), MIN_DOUBLE_EPSILON) if capture_doubles else None
        pole_threshold = get_pole_threshold(bpy.context) if capture_poles else None
        buckets = {}

        for vert in bm.verts:
            if capture_doubles:
                co = vert.co
                key = (
                    round(co.x / double_epsilon),
                    round(co.y / double_epsilon),
                    round(co.z / double_epsilon),
                )
                buckets.setdefault(key, []).append(vert)

            if capture_poles or capture_isolated:
                edge_count = len(vert.link_edges)
                if capture_poles and edge_count > pole_threshold:
                    self.pole_count += 1
                    if self.detailed:
                        self.pole_points.append(_point_payload(vert.co, vert.normal))
                if capture_isolated and edge_count == 0:
                    self.isolated_vert_count += 1
                    if self.detailed:
                        self.isolated_points.append(_point_payload(vert.co, vert.normal))

        if not capture_doubles:
            return

        for verts in buckets.values():
            if len(verts) <= 1:
                continue
            self.double_vert_count += len(verts)
            if not self.detailed:
                continue
            for vert in verts:
                self.double_points.append(_point_payload(vert.co, vert.normal))

    def _capture_edges(self, bm):
        self.non_manifold_count = 0
        self.non_manifold_segments = []
        self.missing_sharp_edge_count = 0
        self.missing_sharp_segments = []
        capture_non_manifold = "NON_MANIFOLD" in self.enabled_ids
        capture_missing_sharp = "MISSING_SHARP" in self.enabled_ids
        if not (capture_non_manifold or capture_missing_sharp):
            return

        threshold = get_missing_sharp_angle_radians(bpy.context) if capture_missing_sharp else None
        skip_marked = get_missing_sharp_skip_marked(bpy.context) if capture_missing_sharp else None

        for edge in bm.edges:
            if len(edge.verts) != 2:
                continue

            is_manifold = edge.is_manifold
            if capture_non_manifold and not is_manifold:
                self.non_manifold_count += 1
                if self.detailed:
                    self.non_manifold_segments.append(
                        (
                            tuple(edge.verts[0].co),
                            tuple(edge.verts[1].co),
                            tuple(edge.verts[0].normal),
                            tuple(edge.verts[1].normal),
                        )
                    )

            if not capture_missing_sharp or not is_manifold or len(edge.link_faces) != 2:
                continue
            if skip_marked and getattr(edge, "smooth", True) is False:
                continue
            try:
                angle = edge.calc_face_angle_signed()
            except (TypeError, ValueError, RuntimeError):
                try:
                    angle = edge.calc_face_angle()
                except (TypeError, ValueError, RuntimeError):
                    angle = 0.0
            if abs(angle) <= threshold:
                continue
            self.missing_sharp_edge_count += 1
            if self.detailed:
                self.missing_sharp_segments.append(
                    (
                        tuple(edge.verts[0].co),
                        tuple(edge.verts[1].co),
                        tuple(edge.verts[0].normal),
                        tuple(edge.verts[1].normal),
                    )
                )

    def has_check_findings(self):
        return any(
            (
                self.ngon_count,
                self.double_vert_count,
                self.long_tri_count,
                self.tiny_face_count,
                self.pole_count,
                self.isolated_vert_count,
                self.non_manifold_count,
                self.missing_sharp_edge_count,
            )
        )

    def to_result_dict(self):
        return {
            "object_name": self.object_name,
            "tris": self.tris,
            "ngon_count": self.ngon_count,
            "double_vert_count": self.double_vert_count,
            "long_tri_count": self.long_tri_count,
            "tiny_face_count": self.tiny_face_count,
            "pole_count": self.pole_count,
            "isolated_vert_count": self.isolated_vert_count,
            "non_manifold_count": self.non_manifold_count,
            "missing_sharp_edge_count": self.missing_sharp_edge_count,
            "has_findings": self.has_check_findings(),
        }

    def to_overlay_payload(self, matrix_world, visible_ids=None):
        visible_ids = _resolve_enabled_ids(visible_ids)
        normal_matrix = matrix_world.to_3x3()

        def transform_normal(normal):
            try:
                return (normal_matrix @ Vector(normal)).normalized()
            except Exception:
                return Vector((0.0, 0.0, 1.0))

        def transform_points(items):
            return [
                {
                    "point": matrix_world @ Vector(coord),
                    "normal": transform_normal(normal),
                }
                for coord, normal in items
            ]

        def transform_faces(items):
            return [
                {
                    "verts": [matrix_world @ Vector(vert) for vert in face["verts"]],
                    "indices": face["indices"],
                    "normal": transform_normal(face["normal"]),
                }
                for face in items
            ]

        return {
            "ngon_faces": transform_faces(self.ngon_faces) if "NGONS" in visible_ids else [],
            "double_points": transform_points(self.double_points) if "DOUBLES" in visible_ids else [],
            "long_tri_faces": transform_faces(self.long_tri_faces) if "LONG_TRIS" in visible_ids else [],
            "long_tri_segments": [
                {
                    "start": matrix_world @ Vector(start),
                    "end": matrix_world @ Vector(end),
                    "start_normal": transform_normal(start_normal),
                    "end_normal": transform_normal(end_normal),
                }
                for start, end, start_normal, end_normal in self.long_tri_segments
            ] if "LONG_TRIS" in visible_ids else [],
            "tiny_face_points": transform_points(self.tiny_face_points) if "TINY_FACES" in visible_ids else [],
            "tiny_face_faces": transform_faces(self.tiny_face_faces) if "TINY_FACES" in visible_ids else [],
            "pole_points": transform_points(self.pole_points) if "POLES" in visible_ids else [],
            "isolated_points": transform_points(self.isolated_points) if "ISOLATED_VERTS" in visible_ids else [],
            "non_manifold_segments": [
                {
                    "start": matrix_world @ Vector(start),
                    "end": matrix_world @ Vector(end),
                    "start_normal": transform_normal(start_normal),
                    "end_normal": transform_normal(end_normal),
                }
                for start, end, start_normal, end_normal in self.non_manifold_segments
            ] if "NON_MANIFOLD" in visible_ids else [],
            "missing_sharp_segments": [
                {
                    "start": matrix_world @ Vector(start),
                    "end": matrix_world @ Vector(end),
                    "start_normal": transform_normal(start_normal),
                    "end_normal": transform_normal(end_normal),
                }
                for start, end, start_normal, end_normal in self.missing_sharp_segments
            ] if "MISSING_SHARP" in visible_ids else [],
        }


def get_geometry_memo(context, obj, depsgraph=None, rebuild=True, enabled_ids=None, detailed=True):
    if obj is None:
        return None

    settings_signature = _get_check_settings_signature(context)
    memo = OBJECT_MEMOS.get(obj.name)
    if memo is not None and not memo.is_stale(
        obj,
        enabled_ids=enabled_ids,
        detailed=detailed,
        settings_signature=settings_signature,
    ):
        return memo

    if not rebuild:
        return None

    if depsgraph is None:
        try:
            depsgraph = context.evaluated_depsgraph_get()
        except (AttributeError, ReferenceError, RuntimeError):
            return None

    memo = CheckGeometryMemo.from_object(
        obj,
        depsgraph,
        enabled_ids=enabled_ids,
        detailed=detailed,
        settings_signature=settings_signature,
    )
    OBJECT_MEMOS[obj.name] = memo
    return memo
