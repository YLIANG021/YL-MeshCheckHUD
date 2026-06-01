import logging

import bmesh
import bpy
from mathutils import Vector

from ..heatmap.logic import get_focused_object, is_heatmap_active
from ..mesh_metrics import count_mesh_triangles, get_evaluated_mesh_data


ADDON_PACKAGE = __package__.rsplit(".", 1)[0]
LOGGER = logging.getLogger(ADDON_PACKAGE or __name__)
DEFAULT_HIGH_POLY_FACE_LIMIT = 100000
UNAPPLIED_SCALE_EPSILON = 0.001
OBJECT_UPDATE_INTERVAL = 0.05
EDIT_UPDATE_INTERVAL = 0.1


CACHE = {
    "data": None,
    "text_layout": {},
    "text_signature": None,
    "is_calculating": False,
    "needs_update": False,
}


def get_prefs():
    """Safely retrieve add-on preferences."""
    try:
        return bpy.context.preferences.addons[ADDON_PACKAGE].preferences
    except (KeyError, AttributeError):
        return None


def _set_cached_data(data):
    """Update cached overlay data and invalidate derived layout."""
    previous_data = CACHE["data"]
    previous_signature = CACHE["text_signature"]
    new_signature = _get_text_signature(data)

    CACHE["data"] = data
    CACHE["text_signature"] = new_signature

    if previous_signature != new_signature:
        CACHE["text_layout"] = {}

    return previous_data != data


def _tag_view3d_redraw(context):
    """Request redraw for every visible 3D View area."""
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return

    for window in window_manager.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _clear_cached_data(context):
    """Clear overlay data and redraw the viewport when visible text should disappear."""
    data_changed = _set_cached_data(None)
    if data_changed:
        _tag_view3d_redraw(context)


def _vector_to_tuple(value, digits=6):
    """Convert a Vector-like value into a rounded tuple for stable comparisons."""
    if value is None:
        return None
    return tuple(round(component, digits) for component in value)


def _get_text_signature(data):
    """Return the subset of data that affects text layout and measurement."""
    if data is None:
        return None

    return (
        data.get("count_label"),
        data.get("tris"),
        _vector_to_tuple(data.get("dims")),
        data.get("show_unapplied_scale"),
        data.get("unapplied_scale"),
        data.get("high_poly"),
        data.get("show_high_poly_threshold"),
        data.get("high_poly_threshold_label"),
        data.get("selected_count"),
        data.get("auto_unit"),
        data.get("unit_sys"),
        data.get("show_units"),
        data.get("font_size"),
        getattr(getattr(bpy.app, "translations", None), "locale", ""),
    )


def _get_high_poly_limit(prefs):
    """Return the active high-poly limit from preferences."""
    if prefs is None:
        return DEFAULT_HIGH_POLY_FACE_LIMIT
    return max(50000, int(getattr(prefs, "high_poly_face_limit", DEFAULT_HIGH_POLY_FACE_LIMIT)))


def _get_update_interval(context):
    """Return the refresh interval for the current mode."""
    if context and getattr(context, "mode", "") == "OBJECT":
        return OBJECT_UPDATE_INTERVAL
    return EDIT_UPDATE_INTERVAL


def _get_selected_meshes(context):
    """Safely return selected mesh objects for normal and restricted contexts."""
    selected_objects = getattr(context, "selected_objects", None)
    if not selected_objects:
        return []
    return [obj for obj in selected_objects if getattr(obj, "type", None) == "MESH"]


def _get_overlay_meshes(context):
    """Return meshes used by the HUD, falling back to the active preview target."""
    selected_meshes = _get_selected_meshes(context)
    if selected_meshes:
        return selected_meshes

    if context and getattr(context, "mode", "") == "OBJECT" and is_heatmap_active(context):
        focused = get_focused_object(context)
        if focused is not None and getattr(focused, "type", None) == "MESH":
            return [focused]

    return []


def _has_any_selection(bm):
    """Return True when any edit-mode element is selected."""
    return (
        any(vert.select for vert in bm.verts)
        or any(edge.select for edge in bm.edges)
        or any(face.select for face in bm.faces)
    )


def _iter_selected_vertices(bm):
    """Yield selected vertices from faces/edges/verts without multiple full scans."""
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    seen = set()

    for face in bm.faces:
        if not face.select:
            continue
        for vert in face.verts:
            vert_index = vert.index
            if vert_index not in seen:
                seen.add(vert_index)
                yield vert

    for edge in bm.edges:
        if not edge.select:
            continue
        for vert in edge.verts:
            vert_index = vert.index
            if vert_index not in seen:
                seen.add(vert_index)
                yield vert

    for vert in bm.verts:
        if vert.select and vert.index not in seen:
            yield vert


def _has_unapplied_scale(obj):
    """Return True when object scale differs from the applied default."""
    scale = obj.scale
    return (
        abs(scale.x - 1.0) > UNAPPLIED_SCALE_EPSILON
        or abs(scale.y - 1.0) > UNAPPLIED_SCALE_EPSILON
        or abs(scale.z - 1.0) > UNAPPLIED_SCALE_EPSILON
    )


def _count_mesh_triangles(mesh, high_poly_limit=DEFAULT_HIGH_POLY_FACE_LIMIT, simplify_high_poly=True):
    """Count triangles exactly, including meshes that contain n-gons."""
    del high_poly_limit
    del simplify_high_poly
    return count_mesh_triangles(mesh)


def _get_object_dimensions(obj, depsgraph):
    """Return evaluated dimensions when available, otherwise original dimensions."""
    try:
        return obj.evaluated_get(depsgraph).dimensions.copy()
    except (AttributeError, ReferenceError, RuntimeError):
        try:
            return obj.dimensions.copy()
        except (AttributeError, ReferenceError, RuntimeError):
            return None


def _format_high_poly_threshold(limit):
    """Return a compact threshold label such as 50k."""
    if limit >= 1000 and limit % 1000 == 0:
        return f"{limit // 1000}k"
    if limit >= 1000:
        return f"{limit / 1000:.1f}k"
    return str(limit)


def get_bmesh_stats(obj, high_poly_limit=DEFAULT_HIGH_POLY_FACE_LIMIT, simplify=True):
    """Return world-space bounds and triangle count for the current edit selection."""
    try:
        bm = bmesh.from_edit_mesh(obj.data)
    except ValueError:
        return None, None, 0, False

    tris_count = 0
    total_faces = len(bm.faces)
    is_high_poly = total_faces > high_poly_limit
    world_mat = obj.matrix_world

    local_min = Vector((float("inf"),) * 3)
    local_max = Vector((float("-inf"),) * 3)
    skip_calc = simplify and is_high_poly

    if not _has_any_selection(bm):
        return None, None, 0, is_high_poly

    for face in bm.faces:
        if face.select:
            tris_count += len(face.verts) - 2

    if not skip_calc:
        has_selection = False
        for vert in _iter_selected_vertices(bm):
            has_selection = True
            co = world_mat @ vert.co
            local_min.x = min(local_min.x, co.x)
            local_min.y = min(local_min.y, co.y)
            local_min.z = min(local_min.z, co.z)
            local_max.x = max(local_max.x, co.x)
            local_max.y = max(local_max.y, co.y)
            local_max.z = max(local_max.z, co.z)

        if not has_selection:
            return None, None, tris_count, is_high_poly

    if skip_calc:
        return None, None, tris_count, is_high_poly

    return local_min, local_max, tris_count, is_high_poly


def update_data():
    """Refresh cached overlay data."""
    CACHE["is_calculating"] = True
    CACHE["needs_update"] = False
    try:
        context = bpy.context
        if not context or not context.preferences:
            _clear_cached_data(context)
            return

        prefs = get_prefs()
        if not prefs or not prefs.enable_display:
            _clear_cached_data(context)
            return

        selected_meshes = _get_overlay_meshes(context)
        if not selected_meshes:
            _clear_cached_data(context)
            return

        try:
            depsgraph = context.evaluated_depsgraph_get()
        except (AttributeError, ReferenceError, RuntimeError):
            _clear_cached_data(context)
            return

        high_poly_limit = _get_high_poly_limit(prefs)

        total_tris = 0
        global_min = Vector((float("inf"),) * 3)
        global_max = Vector((float("-inf"),) * 3)
        has_valid_bounds = False
        has_unapplied_scale = False
        high_poly_warning = False
        mode = context.mode
        is_single_object_mode = mode == "OBJECT" and len(selected_meshes) == 1

        for obj in selected_meshes:
            if _has_unapplied_scale(obj):
                has_unapplied_scale = True

            if mode == "EDIT_MESH" and obj.mode == "EDIT":
                min_v, max_v, obj_tris, is_high_poly = get_bmesh_stats(
                    obj,
                    high_poly_limit=high_poly_limit,
                    simplify=True,
                )
                if is_high_poly:
                    high_poly_warning = True
                total_tris += obj_tris
                if min_v is not None:
                    has_valid_bounds = True
                    global_min.x = min(global_min.x, min_v.x)
                    global_min.y = min(global_min.y, min_v.y)
                    global_min.z = min(global_min.z, min_v.z)
                    global_max.x = max(global_max.x, max_v.x)
                    global_max.y = max(global_max.y, max_v.y)
                    global_max.z = max(global_max.z, max_v.z)
                continue

            eval_obj, mesh = get_evaluated_mesh_data(obj, depsgraph)
            if mesh is None or eval_obj is None:
                continue

            total_tris += _count_mesh_triangles(mesh, high_poly_limit=high_poly_limit, simplify_high_poly=True)

            if is_single_object_mode or eval_obj.dimensions.length <= 0:
                continue

            has_valid_bounds = True
            matrix_world = eval_obj.matrix_world
            for corner in eval_obj.bound_box:
                world_co = matrix_world @ Vector(corner)
                global_min.x = min(global_min.x, world_co.x)
                global_min.y = min(global_min.y, world_co.y)
                global_min.z = min(global_min.z, world_co.z)
                global_max.x = max(global_max.x, world_co.x)
                global_max.y = max(global_max.y, world_co.y)
                global_max.z = max(global_max.z, world_co.z)

        final_dims = None
        if is_single_object_mode:
            obj = selected_meshes[0]
            final_dims = _get_object_dimensions(obj, depsgraph)
        elif has_valid_bounds:
            final_dims = global_max - global_min

        result_data = {
            "dims": final_dims,
            "tris": total_tris,
            "count_label": "Tris",
            "selected_count": len(selected_meshes),
            "show_unapplied_scale": prefs.show_unapplied_scale,
            "unapplied_scale": has_unapplied_scale,
            "show_high_poly_threshold": prefs.show_high_poly_threshold,
            "high_poly": high_poly_warning,
            "high_poly_threshold_label": _format_high_poly_threshold(high_poly_limit),
            "auto_unit": prefs.auto_unit,
            "font_size": prefs.font_size,
            "unit_sys": prefs.unit_system,
            "show_units": prefs.show_units,
        }
        data_changed = _set_cached_data(result_data)

        if data_changed:
            _tag_view3d_redraw(context)

    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as exc:
        LOGGER.exception("Failed to refresh overlay data: %s", exc)
        _clear_cached_data(bpy.context)
    finally:
        CACHE["is_calculating"] = False


def deferred_update():
    """Timer callback used to debounce data refreshes."""
    context = bpy.context
    if not context:
        CACHE["needs_update"] = False
        return None

    interval = _get_update_interval(context)

    prefs = get_prefs()
    if not prefs or not getattr(prefs, "enable_display", False):
        CACHE["needs_update"] = False
        _clear_cached_data(context)
        return None

    if CACHE["is_calculating"]:
        return interval

    # Edit-mode element selection changes do not reliably trigger depsgraph updates,
    # so keep the HUD refreshed on a lightweight timer while it is enabled.
    CACHE["needs_update"] = True

    update_data()
    return interval


@bpy.app.handlers.persistent
def tag_update_dirty(scene=None, depsgraph=None):
    """Mark cached data dirty and schedule a refresh."""
    del scene
    del depsgraph
    context = bpy.context
    if not context:
        return

    prefs = get_prefs()
    if prefs and not prefs.enable_display:
        _clear_cached_data(context)
        return

    CACHE["needs_update"] = True

    if CACHE["is_calculating"]:
        return
    if not bpy.app.timers.is_registered(deferred_update):
        bpy.app.timers.register(deferred_update, first_interval=_get_update_interval(context))
