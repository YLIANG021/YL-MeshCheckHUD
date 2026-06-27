from mathutils import Vector

from .config import (
    get_double_epsilon,
    get_enabled_check_ids,
    get_long_tri_degenerate_epsilon,
    get_long_tri_ratio_threshold,
    get_missing_sharp_angle_radians,
    get_missing_sharp_skip_marked,
    get_pole_threshold,
    get_tiny_face_area_threshold,
    get_visible_check_ids,
)
from .geometry import (
    MIN_DOUBLE_EPSILON,
    _get_edit_bmesh,
    _safe_triangles,
    _triangle_long_ratio,
    get_geometry_memo,
)
from .limits import (
    MAX_FACE_PRIMITIVES,
    MAX_POINT_PRIMITIVES,
    MAX_SEGMENT_PRIMITIVES,
)
from .runtime import (
    CHECK_CACHE,
    RUNNING_CHECK_KEY,
    _empty_overlay_payload,
    _store_check_overlay_cache,
    _store_edit_check_overlay_cache,
)


def _get_matrix_signature(matrix_world):
    if matrix_world is None:
        return None
    return tuple(round(value, 8) for row in matrix_world for value in row)


def _active_mesh_object(context):
    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if active_object is None or getattr(active_object, "type", None) != 'MESH':
        return None
    return active_object


def _transform_edit_normal_payload_fast(normal_matrix, normal):
    try:
        return (normal_matrix @ Vector(normal)).normalized()
    except Exception:
        return Vector((0.0, 0.0, 1.0))


def _transform_edit_point_payload_fast(matrix_world, normal_matrix, coord, normal):
    try:
        point = matrix_world @ Vector(coord)
    except Exception:
        point = Vector(coord)

    transformed_normal = _transform_edit_normal_payload_fast(normal_matrix, normal)

    return {
        "point": point,
        "normal": transformed_normal,
    }


def _transform_edit_segment_payload_fast(matrix_world, normal_matrix, start, end, start_normal, end_normal):
    try:
        start_point = matrix_world @ Vector(start)
        end_point = matrix_world @ Vector(end)
    except Exception:
        start_point = Vector(start)
        end_point = Vector(end)

    start_n = _transform_edit_normal_payload_fast(normal_matrix, start_normal)
    end_n = _transform_edit_normal_payload_fast(normal_matrix, end_normal)

    return {
        "start": start_point,
        "end": end_point,
        "start_normal": start_n,
        "end_normal": end_n,
    }


def _transform_edit_edge_payload_fast(matrix_world, normal_matrix, edge):
    start_vert, end_vert = edge.verts
    return {
        "start": matrix_world @ start_vert.co,
        "end": matrix_world @ end_vert.co,
        "start_normal": _transform_edit_normal_payload_fast(normal_matrix, start_vert.normal),
        "end_normal": _transform_edit_normal_payload_fast(normal_matrix, end_vert.normal),
    }


def _transform_edit_triangle_segments_payload_fast(matrix_world, normal_matrix, a, b, c, normal):
    try:
        a_point = matrix_world @ a
        b_point = matrix_world @ b
        c_point = matrix_world @ c
    except Exception:
        a_point = Vector(a)
        b_point = Vector(b)
        c_point = Vector(c)

    transformed_normal = _transform_edit_normal_payload_fast(normal_matrix, normal)

    return (
        {
            "start": a_point,
            "end": b_point,
            "start_normal": transformed_normal,
            "end_normal": transformed_normal,
        },
        {
            "start": b_point,
            "end": c_point,
            "start_normal": transformed_normal,
            "end_normal": transformed_normal,
        },
        {
            "start": c_point,
            "end": a_point,
            "start_normal": transformed_normal,
            "end_normal": transformed_normal,
        },
    )


def _transform_edit_face_payload_fast(matrix_world, normal_matrix, verts, indices, normal):
    transformed_verts = [matrix_world @ Vector(vert) for vert in verts]
    transformed_normal = _transform_edit_normal_payload_fast(normal_matrix, normal)

    return {
        "verts": transformed_verts,
        "indices": indices,
        "normal": transformed_normal,
    }


def _edit_topology_signature(bm):
    return (len(bm.verts), len(bm.edges), len(bm.faces))


def _build_edit_mode_overlay_payload(context, active_object, visible_ids, bm=None):
    if bm is None:
        bm = _get_edit_bmesh(active_object)
    if bm is None:
        return None

    payload = _empty_overlay_payload()
    payload["_edit_dynamic_object"] = active_object.name
    payload["_edit_topology_signature"] = _edit_topology_signature(bm)
    matrix_world = active_object.matrix_world
    normal_matrix = matrix_world.to_3x3()
    visible_ids = set(visible_ids)

    capture_ngons = "NGONS" in visible_ids
    capture_doubles = "DOUBLES" in visible_ids
    capture_long_tris = "LONG_TRIS" in visible_ids
    capture_tiny_faces = "TINY_FACES" in visible_ids
    capture_poles = "POLES" in visible_ids
    capture_isolated = "ISOLATED_VERTS" in visible_ids
    ngon_faces = []
    if capture_ngons or capture_long_tris or capture_tiny_faces:
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.verts.index_update()
        bm.faces.index_update()

    if capture_ngons or capture_long_tris or capture_tiny_faces:
        long_tri_threshold = get_long_tri_ratio_threshold(context) if capture_long_tris else None
        tiny_face_threshold = get_tiny_face_area_threshold(context) if capture_tiny_faces else None
        zero_face_epsilon = get_long_tri_degenerate_epsilon() if capture_long_tris else None

        for face in bm.faces:
            face_vert_count = len(face.verts)

            if capture_ngons and face_vert_count > 4 and len(ngon_faces) < MAX_FACE_PRIMITIVES:
                verts = [tuple(vert.co) for vert in face.verts]
                ngon_faces.append(
                    _transform_edit_face_payload_fast(
                        matrix_world,
                        normal_matrix,
                        verts,
                        tuple(_safe_triangles(verts)),
                        tuple(face.normal),
                    )
                )

            if capture_tiny_faces and face.calc_area() <= tiny_face_threshold:
                if len(payload["tiny_face_points"]) < MAX_POINT_PRIMITIVES:
                    payload["tiny_face_points"].append(
                        _transform_edit_point_payload_fast(
                            matrix_world,
                            normal_matrix,
                            tuple(face.calc_center_median()),
                            tuple(face.normal),
                        )
                    )

            if not capture_long_tris or face_vert_count != 3:
                continue

            a = face.verts[0].co
            b = face.verts[1].co
            c = face.verts[2].co
            ratio = _triangle_long_ratio(a, b, c, zero_face_epsilon)
            if ratio < long_tri_threshold:
                continue

            if len(payload["long_tri_segments"]) >= MAX_SEGMENT_PRIMITIVES - 2:
                continue

            face_normal = tuple(face.normal)
            payload["long_tri_segments"].extend(
                _transform_edit_triangle_segments_payload_fast(
                    matrix_world,
                    normal_matrix,
                    a,
                    b,
                    c,
                    face_normal,
                )
            )

    if capture_ngons:
        payload["ngon_faces"] = ngon_faces

    if capture_doubles or capture_long_tris or capture_tiny_faces or capture_poles or capture_isolated:
        double_epsilon = max(get_double_epsilon(context), MIN_DOUBLE_EPSILON) if capture_doubles else None
        pole_threshold = get_pole_threshold(context) if capture_poles else None
        buckets = {}
        double_indices = []
        pole_indices = []
        isolated_indices = []

        if capture_doubles or capture_poles or capture_isolated:
            bm.verts.ensure_lookup_table()
            bm.verts.index_update()

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
                    if len(pole_indices) < MAX_POINT_PRIMITIVES:
                        pole_indices.append(vert.index)
                if capture_isolated and edge_count == 0:
                    if len(isolated_indices) < MAX_POINT_PRIMITIVES:
                        isolated_indices.append(vert.index)

        if capture_poles:
            payload["pole_points"] = [
                _transform_edit_point_payload_fast(
                    matrix_world,
                    normal_matrix,
                    tuple(bm.verts[index].co),
                    tuple(bm.verts[index].normal),
                )
                for index in pole_indices
            ]
        if capture_isolated:
            payload["isolated_points"] = [
                _transform_edit_point_payload_fast(
                    matrix_world,
                    normal_matrix,
                    tuple(bm.verts[index].co),
                    tuple(bm.verts[index].normal),
                )
                for index in isolated_indices
            ]

        if capture_doubles:
            for verts in buckets.values():
                if len(verts) <= 1:
                    continue
                for vert in verts:
                    if len(double_indices) < MAX_POINT_PRIMITIVES:
                        double_indices.append(vert.index)
            payload["double_points"] = [
                _transform_edit_point_payload_fast(
                    matrix_world,
                    normal_matrix,
                    tuple(bm.verts[index].co),
                    tuple(bm.verts[index].normal),
                )
                for index in double_indices
            ]

    capture_non_manifold = "NON_MANIFOLD" in visible_ids
    capture_missing_sharp = "MISSING_SHARP" in visible_ids
    if capture_non_manifold or capture_missing_sharp:
        threshold = get_missing_sharp_angle_radians(context) if capture_missing_sharp else None
        skip_marked = get_missing_sharp_skip_marked(context) if capture_missing_sharp else None
        non_manifold_edge_indices = []

        if capture_non_manifold or capture_missing_sharp:
            bm.edges.ensure_lookup_table()
            bm.edges.index_update()

        for edge in bm.edges:
            if len(edge.verts) != 2:
                continue
            is_manifold = edge.is_manifold

            if capture_non_manifold and not is_manifold:
                if len(non_manifold_edge_indices) < MAX_SEGMENT_PRIMITIVES:
                    non_manifold_edge_indices.append(edge.index)

            if (
                not capture_missing_sharp
                or len(payload["missing_sharp_segments"]) >= MAX_SEGMENT_PRIMITIVES
                or not is_manifold
                or len(edge.link_faces) != 2
            ):
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
            payload["missing_sharp_segments"].append(
                _transform_edit_edge_payload_fast(matrix_world, normal_matrix, edge)
            )

        if capture_non_manifold:
            payload["non_manifold_segments"] = [
                _transform_edit_edge_payload_fast(matrix_world, normal_matrix, bm.edges[index])
                for index in non_manifold_edge_indices
            ]

    return payload


def get_active_check_overlay_data(context, get_active_check_object_name):
    scene = getattr(context, "scene", None)
    if scene is not None and scene.get(RUNNING_CHECK_KEY):
        return None

    object_name = get_active_check_object_name(context)
    if not object_name:
        return None

    obj = context.view_layer.objects.get(object_name)
    matrix_signature = _get_matrix_signature(obj.matrix_world) if obj is not None else None
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    prefs_signature = ""
    visible_ids = []
    if settings is not None:
        visible_ids = get_visible_check_ids(settings)
        prefs_signature = ",".join(visible_ids)
        enabled_ids = get_enabled_check_ids(settings)
    else:
        enabled_ids = []

    if (
        not CHECK_CACHE["dirty"]
        and CHECK_CACHE["object_name"] == object_name
        and CHECK_CACHE["matrix_signature"] == matrix_signature
        and CHECK_CACHE["prefs_signature"] == prefs_signature
        and CHECK_CACHE["data"] is not None
    ):
        return CHECK_CACHE["data"]

    memo = (
        get_geometry_memo(
            context,
            obj,
            rebuild=True,
            enabled_ids=enabled_ids,
            detailed=True,
        )
        if obj is not None
        else None
    )
    data = memo.to_overlay_payload(obj.matrix_world, visible_ids=visible_ids) if memo is not None and obj is not None else None
    _store_check_overlay_cache(object_name, matrix_signature, prefs_signature, data)
    return data


def get_edit_mode_active_check_overlay_data(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or settings.mode != 'CHECK' or not settings.show_overlay:
        return None

    active_object = _active_mesh_object(context)
    if active_object is None or not getattr(getattr(active_object, "data", None), "is_editmode", False):
        return None

    visible_ids = get_visible_check_ids(settings)
    if not visible_ids:
        return None
    matrix_signature = _get_matrix_signature(active_object.matrix_world)
    prefs_signature = ",".join(visible_ids)

    if (
        not CHECK_CACHE["edit_dirty"]
        and CHECK_CACHE["edit_object_name"] == active_object.name
        and CHECK_CACHE["edit_matrix_signature"] == matrix_signature
        and CHECK_CACHE["edit_prefs_signature"] == prefs_signature
        and CHECK_CACHE["edit_data"] is not None
    ):
        return CHECK_CACHE["edit_data"]

    return None
