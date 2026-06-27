import time

import bpy
import bmesh
from .draw import draw_callback_view
from .core.results import (
    clear_check_results,
    clear_preview_results,
    refresh_edit_mode_active_check_overlay,
    refresh_edit_mode_active_check_result,
    sync_results_to_active_object,
)
from .core.runtime import (
    ACTIVE_OBJECT_SYNC_KEY,
    CHECK_CACHE,
    CHECK_SCENE_DIRTY_KEY,
    CHECK_LIST_SYNC_KEY,
    OWNER_AREA_KEY,
    RUNTIME_CACHE,
    CHECK_REFRESH_SIGNATURE_KEY,
    RUNNING_CHECK_KEY,
    RUNNING_PREVIEW_KEY,
    invalidate_geometry_memos,
    invalidate_check_cache,
    invalidate_preview_cache,
    mark_runtime_objects_dirty,
    PREVIEW_REFRESH_SIGNATURE_KEY,
    PREVIEW_LIST_SYNC_KEY,
)
from .operators import refresh_meshcheck_results
from .core.config import (
    get_double_epsilon,
    get_long_tri_degenerate_epsilon,
    get_long_tri_ratio_threshold,
    get_tiny_face_area_threshold,
    get_visible_check_ids,
)
from .core.geometry import MIN_DOUBLE_EPSILON, _triangle_long_ratio
from ..overlay.core import get_prefs


DRAW_HANDLER_VIEW = None
AUTO_REFRESH_SELECTION_KEY = "_yl_meshcheck_auto_refresh_selection"
EDIT_MODE_REALTIME_TRI_LIMIT_DEFAULT = 25000
ACTIVE_CHECK_SIGNATURE_KEY = "_yl_meshcheck_active_check_signature"
ACTIVE_CHECK_OBJECT_KEY = "_yl_meshcheck_active_check_object"
PREVIOUS_CONTEXT_MODE_KEY = "_yl_meshcheck_previous_context_mode"
DEPSGRAPH_SCAN_INTERVAL = 0.03
EDIT_SHAPE_SIGNATURE_MAX_SCAN = 4096
EDIT_SHAPE_SIGNATURE_DIGITS = 5
EDIT_SHAPE_SIGNATURE_SCALE = 10 ** EDIT_SHAPE_SIGNATURE_DIGITS
EDIT_PROBLEM_SIGNATURE_CHECK_IDS = frozenset(("DOUBLES", "LONG_TRIS", "TINY_FACES"))
EDIT_TOPOLOGY_SIGNATURE_CACHE = {}
EDIT_SHAPE_SIGNATURE_CACHE = {}
DEPSGRAPH_SCAN_STATE = {
    "last_scan_time": 0.0,
}
SAVE_RUNTIME_STATE_SNAPSHOT = {}
SCENE_RUNTIME_KEYS = (
    ACTIVE_OBJECT_SYNC_KEY,
    AUTO_REFRESH_SELECTION_KEY,
    ACTIVE_CHECK_SIGNATURE_KEY,
    ACTIVE_CHECK_OBJECT_KEY,
    PREVIEW_REFRESH_SIGNATURE_KEY,
    CHECK_REFRESH_SIGNATURE_KEY,
    CHECK_SCENE_DIRTY_KEY,
    CHECK_LIST_SYNC_KEY,
    PREVIEW_LIST_SYNC_KEY,
    OWNER_AREA_KEY,
    RUNNING_CHECK_KEY,
    RUNNING_PREVIEW_KEY,
    PREVIOUS_CONTEXT_MODE_KEY,
)


def _cleanup_handlers():
    return getattr(bpy.app.handlers, "exit_pre", None)


def _scene_pointer(scene):
    if scene is None:
        return 0
    try:
        return int(scene.as_pointer())
    except (ReferenceError, RuntimeError, TypeError, ValueError):
        return 0


def _clear_scene_runtime_keys(scene):
    if scene is None:
        return
    for key in SCENE_RUNTIME_KEYS:
        if key in scene:
            del scene[key]


def _get_selected_mesh_signature(context):
    if context is None:
        return ""

    selected_meshes = [
        obj.name
        for obj in getattr(context, "selected_objects", [])
        if getattr(obj, "type", None) == 'MESH'
    ]
    selected_meshes.sort()
    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    active_name = active_object.name if active_object is not None and getattr(active_object, "type", None) == 'MESH' else ""
    return "|".join((context.mode, active_name, *selected_meshes))


def _get_active_check_signature(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if context is None or scene is None or settings is None:
        return ""
    if settings.mode != 'CHECK' or not settings.show_overlay:
        return ""

    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if active_object is None or getattr(active_object, "type", None) != 'MESH' or getattr(active_object, "data", None) is None:
        return ""

    active_name = active_object.name
    if settings.check_results and not any(item.object_name == active_name for item in settings.check_results):
        return ""
    mesh = active_object.data

    return "|".join(
        (
            getattr(context, "mode", ""),
            active_name,
            str(int(mesh.as_pointer())),
            str(len(getattr(mesh, "vertices", ()))),
            str(len(getattr(mesh, "edges", ()))),
            str(len(getattr(mesh, "polygons", ()))),
        )
    )


def _get_edit_mode_realtime_tri_limit():
    prefs = get_prefs()
    if prefs is None:
        return EDIT_MODE_REALTIME_TRI_LIMIT_DEFAULT
    try:
        return max(
            10000,
            min(
                100000,
                int(
                    getattr(
                        prefs,
                        "meshcheck_edit_realtime_tri_limit",
                        EDIT_MODE_REALTIME_TRI_LIMIT_DEFAULT,
                    )
                ),
            ),
        )
    except (TypeError, ValueError):
        return EDIT_MODE_REALTIME_TRI_LIMIT_DEFAULT


def _get_active_mesh_name(context):
    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if active_object is None or getattr(active_object, "type", None) != 'MESH':
        return "", None
    return active_object.name, active_object


def _is_mesh_geometry_update(update):
    update_id = getattr(update, "id", None)
    if isinstance(update_id, bpy.types.Object):
        return (
            getattr(update_id, "type", None) == 'MESH'
            and getattr(update_id, "data", None) is not None
            and bool(getattr(update, "is_updated_geometry", False))
        )
    return isinstance(update_id, bpy.types.Mesh)


def _depsgraph_has_mesh_geometry_update(depsgraph):
    if depsgraph is None:
        return False
    return any(_is_mesh_geometry_update(update) for update in depsgraph.updates)


def _can_scan_depsgraph_now():
    now = time.perf_counter()
    if now - DEPSGRAPH_SCAN_STATE["last_scan_time"] < DEPSGRAPH_SCAN_INTERVAL:
        return False
    DEPSGRAPH_SCAN_STATE["last_scan_time"] = now
    return True


def _mesh_object_names_by_mesh(context):
    view_layer = getattr(context, "view_layer", None)
    objects = getattr(view_layer, "objects", ()) if view_layer is not None else ()
    names_by_mesh = {}
    for obj in objects:
        if getattr(obj, "type", None) != 'MESH':
            continue
        mesh = getattr(obj, "data", None)
        if mesh is None:
            continue
        names_by_mesh.setdefault(mesh, set()).add(obj.name)
    return names_by_mesh


def _collect_depsgraph_changed_mesh_objects(context, depsgraph):
    if depsgraph is None:
        return set()

    changed_object_names = set()
    mesh_updates = []
    for update in depsgraph.updates:
        update_id = getattr(update, "id", None)
        if isinstance(update_id, bpy.types.Object):
            if _is_mesh_geometry_update(update):
                changed_object_names.add(update_id.name)
            continue
        if isinstance(update_id, bpy.types.Mesh):
            mesh_updates.append(update_id)

    if mesh_updates:
        names_by_mesh = _mesh_object_names_by_mesh(context)
        for mesh in mesh_updates:
            changed_object_names.update(names_by_mesh.get(mesh, ()))
    return changed_object_names


def _get_active_edit_topology_signature(active_object):
    mesh = getattr(active_object, "data", None) if active_object is not None else None
    if mesh is None or not getattr(mesh, "is_editmode", False):
        return ()
    try:
        bm = bmesh.from_edit_mesh(mesh)
    except (AttributeError, ReferenceError, RuntimeError, ValueError):
        return ()
    return (len(bm.verts), len(bm.edges), len(bm.faces))


def _get_active_edit_topology_cache_key(active_object):
    mesh = getattr(active_object, "data", None) if active_object is not None else None
    if active_object is None or mesh is None:
        return ()
    try:
        return (int(active_object.as_pointer()), int(mesh.as_pointer()))
    except (ReferenceError, RuntimeError, TypeError, ValueError):
        return ()


def _has_active_edit_topology_changed(active_object):
    signature = _get_active_edit_topology_signature(active_object)
    if not signature:
        return False

    key = _get_active_edit_topology_cache_key(active_object)
    if not key:
        return False

    previous = EDIT_TOPOLOGY_SIGNATURE_CACHE.get(key)
    if previous is None and CHECK_CACHE.get("edit_object_name") == active_object.name:
        previous = tuple(CHECK_CACHE.get("edit_quick_signature", ()))
    if previous == signature:
        EDIT_TOPOLOGY_SIGNATURE_CACHE[key] = signature
        return False

    EDIT_TOPOLOGY_SIGNATURE_CACHE[key] = signature
    return previous is not None


def _quantized_edit_coord_signature(co):
    return (
        int(round(co.x * EDIT_SHAPE_SIGNATURE_SCALE)),
        int(round(co.y * EDIT_SHAPE_SIGNATURE_SCALE)),
        int(round(co.z * EDIT_SHAPE_SIGNATURE_SCALE)),
    )


def _mix_edit_coord_hash(checksum, index, coord_signature):
    qx, qy, qz = coord_signature
    coord_hash = (
        ((qx & 0xFFFFFFFF) * 73856093)
        ^ ((qy & 0xFFFFFFFF) * 19349663)
        ^ ((qz & 0xFFFFFFFF) * 83492791)
        ^ (index * 2654435761)
    )
    return ((checksum ^ coord_hash) * 1099511628211) & 0xFFFFFFFFFFFFFFFF


def _mix_edit_int_hash(checksum, value):
    return ((checksum ^ (int(value) & 0xFFFFFFFFFFFFFFFF)) * 1099511628211) & 0xFFFFFFFFFFFFFFFF


def _get_active_edit_visible_ids():
    scene = getattr(bpy.context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return set()
    return set(get_visible_check_ids(settings))


def _get_active_edit_problem_geometry_signature(bm, visible_ids):
    if not (visible_ids & EDIT_PROBLEM_SIGNATURE_CHECK_IDS):
        return ()

    capture_long_tris = "LONG_TRIS" in visible_ids
    capture_tiny_faces = "TINY_FACES" in visible_ids
    capture_doubles = "DOUBLES" in visible_ids

    long_tri_count = 0
    long_tri_hash = 1469598103934665603
    tiny_face_count = 0
    tiny_face_hash = 1469598103934665603
    double_vert_count = 0
    double_hash = 1469598103934665603

    if capture_long_tris or capture_tiny_faces:
        long_tri_threshold = get_long_tri_ratio_threshold(bpy.context) if capture_long_tris else None
        tiny_face_threshold = get_tiny_face_area_threshold(bpy.context) if capture_tiny_faces else None
        zero_face_epsilon = get_long_tri_degenerate_epsilon() if capture_long_tris else None
        try:
            bm.faces.ensure_lookup_table()
            bm.faces.index_update()
        except (AttributeError, ReferenceError, RuntimeError):
            pass

        for face in bm.faces:
            face_index = getattr(face, "index", 0)
            if capture_tiny_faces:
                area = face.calc_area()
                area_signature = int(round(area * EDIT_SHAPE_SIGNATURE_SCALE * 1000))
                if area <= tiny_face_threshold:
                    tiny_face_count += 1
                    tiny_face_hash = _mix_edit_int_hash(tiny_face_hash, face_index)
                    tiny_face_hash = _mix_edit_int_hash(tiny_face_hash, area_signature)

            if capture_long_tris and len(face.verts) == 3:
                a = face.verts[0].co
                b = face.verts[1].co
                c = face.verts[2].co
                ratio = _triangle_long_ratio(a, b, c, zero_face_epsilon)
                ratio_signature = int(round(min(ratio, 1000000.0) * EDIT_SHAPE_SIGNATURE_SCALE))
                if ratio >= long_tri_threshold:
                    long_tri_count += 1
                    long_tri_hash = _mix_edit_int_hash(long_tri_hash, face_index)
                    long_tri_hash = _mix_edit_int_hash(long_tri_hash, ratio_signature)

    if capture_doubles:
        double_epsilon = max(get_double_epsilon(bpy.context), MIN_DOUBLE_EPSILON)
        buckets = {}
        try:
            bm.verts.ensure_lookup_table()
            bm.verts.index_update()
        except (AttributeError, ReferenceError, RuntimeError):
            pass

        for vert in bm.verts:
            co = vert.co
            key = (
                round(co.x / double_epsilon),
                round(co.y / double_epsilon),
                round(co.z / double_epsilon),
            )
            buckets.setdefault(key, []).append(getattr(vert, "index", 0))

        for key, indices in buckets.items():
            if len(indices) <= 1:
                continue
            double_vert_count += len(indices)
            double_hash = _mix_edit_int_hash(double_hash, key[0])
            double_hash = _mix_edit_int_hash(double_hash, key[1])
            double_hash = _mix_edit_int_hash(double_hash, key[2])
            for index in indices[:8]:
                double_hash = _mix_edit_int_hash(double_hash, index)

    return (
        ("long_tris", long_tri_count, long_tri_hash),
        ("tiny_faces", tiny_face_count, tiny_face_hash),
        ("doubles", double_vert_count, double_hash),
    )


def _get_active_edit_shape_signature(active_object):
    mesh = getattr(active_object, "data", None) if active_object is not None else None
    if mesh is None or not getattr(mesh, "is_editmode", False):
        return None
    try:
        bm = bmesh.from_edit_mesh(mesh)
    except (AttributeError, ReferenceError, RuntimeError, ValueError):
        return None

    visible_ids = _get_active_edit_visible_ids()
    problem_signature = _get_active_edit_problem_geometry_signature(bm, visible_ids)

    scanned_count = 0
    first = None
    middle = None
    last = None
    sum_x = 0.0
    sum_y = 0.0
    sum_z = 0.0
    checksum = 1469598103934665603

    for index, vert in enumerate(bm.verts):
        scanned_count += 1
        coord = vert.co
        coord_signature = _quantized_edit_coord_signature(coord)
        if first is None:
            first = coord_signature
        if scanned_count == (EDIT_SHAPE_SIGNATURE_MAX_SCAN // 2):
            middle = coord_signature
        last = coord_signature
        sum_x += coord_signature[0]
        sum_y += coord_signature[1]
        sum_z += coord_signature[2]
        checksum = _mix_edit_coord_hash(checksum, index, coord_signature)
        if scanned_count >= EDIT_SHAPE_SIGNATURE_MAX_SCAN:
            break

    if scanned_count <= 0:
        return (0,)

    if middle is None:
        middle = last

    return (
        scanned_count,
        first,
        middle,
        last,
        (sum_x, sum_y, sum_z),
        checksum,
        problem_signature,
    )


def _has_active_edit_shape_changed(active_object):
    key = _get_active_edit_topology_cache_key(active_object)
    if not key:
        return False

    signature = _get_active_edit_shape_signature(active_object)
    if signature is None:
        return False

    previous = EDIT_SHAPE_SIGNATURE_CACHE.get(key)
    EDIT_SHAPE_SIGNATURE_CACHE[key] = signature
    return previous is not None and previous != signature


def _has_active_edit_mesh_check_refresh_changed(active_object):
    if _has_active_edit_topology_changed(active_object):
        return True
    if _has_active_edit_shape_changed(active_object):
        return True
    return False


def _prime_active_edit_mesh_check_signature(active_object):
    key = _get_active_edit_topology_cache_key(active_object)
    if not key:
        return

    topology_signature = _get_active_edit_topology_signature(active_object)
    if topology_signature:
        EDIT_TOPOLOGY_SIGNATURE_CACHE[key] = topology_signature
    shape_signature = _get_active_edit_shape_signature(active_object)
    if shape_signature is not None:
        EDIT_SHAPE_SIGNATURE_CACHE[key] = shape_signature


def _should_check_edit_geometry_signature(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    return (
        getattr(context, "mode", "") == 'EDIT_MESH'
        and settings is not None
        and settings.mode == 'CHECK'
        and settings.show_overlay
        and bool(settings.check_results)
    )


def _get_cached_active_tri_count(context, active_name):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or not active_name:
        return 0

    for item in getattr(settings, "check_results", ()):
        if getattr(item, "object_name", "") != active_name:
            continue
        try:
            return max(0, int(getattr(item, "tris", 0)))
        except (TypeError, ValueError):
            return 0
    return 0


def _estimate_active_mesh_triangle_count(context):
    active_name, active_object = _get_active_mesh_name(context)
    if active_object is None:
        return 0

    cached_tri_count = _get_cached_active_tri_count(context, active_name)
    if cached_tri_count > 0:
        return cached_tri_count

    mesh = getattr(active_object, "data", None)
    if mesh is None:
        return 0

    loop_triangles = getattr(mesh, "loop_triangles", None)
    if loop_triangles:
        try:
            return len(loop_triangles)
        except (TypeError, AttributeError):
            pass

    try:
        poly_count = len(getattr(mesh, "polygons", ()))
    except (TypeError, AttributeError):
        return 0

    # Fallback to a cheap upper-bound estimate so large meshes still prefer
    # the safer debounced path when exact triangle data is unavailable.
    return max(0, poly_count * 2)


def _should_refresh_edit_mode_active_check_realtime(context):
    return _estimate_active_mesh_triangle_count(context) <= _get_edit_mode_realtime_tri_limit()


def _scene_needs_cleanup(scene):
    if scene is None:
        return False

    settings = getattr(scene, "yl_omnihud_meshcheck", None)
    if settings is not None and (
        settings.preview_results
        or settings.check_results
        or settings.show_overlay
        or settings.check_use_xray
        or settings.mode != 'PREVIEW'
        or settings.scope != 'VISIBLE'
    ):
        return True

    return any(key in scene for key in SCENE_RUNTIME_KEYS)


def _should_refresh_edit_overlay_from_depsgraph(context, changed_object_names):
    if not _is_active_edit_check_object_changed(context, changed_object_names):
        return False

    if not _has_visible_edit_refresh_sensitive_checks(context):
        return False

    return True


def _refresh_edit_overlay_from_depsgraph(context, changed_object_names):
    if not _should_refresh_edit_overlay_from_depsgraph(context, changed_object_names):
        return False

    if _should_refresh_edit_mode_active_check_realtime(context):
        refresh_edit_mode_active_check_result(context)
    else:
        refresh_edit_mode_active_check_overlay(context)
    return True


def _has_visible_edit_refresh_sensitive_checks(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return False
    return bool(get_visible_check_ids(settings))


def _is_active_edit_check_object_changed(context, changed_object_names):
    if not changed_object_names or getattr(context, "mode", "") != 'EDIT_MESH':
        return False

    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or settings.mode != 'CHECK' or not settings.show_overlay:
        return False

    active_name, _active_object = _get_active_mesh_name(context)
    if not active_name or active_name not in changed_object_names:
        return False

    return True


def _process_object_mode_depsgraph_update(
    context,
    changed_object_names,
    edit_to_object,
    force_check_scene_dirty,
):
    scene = getattr(context, "scene", None)
    if scene is None:
        return

    settings = getattr(scene, "yl_omnihud_meshcheck", None)
    current_mode = getattr(context, "mode", "")
    if force_check_scene_dirty:
        scene[CHECK_SCENE_DIRTY_KEY] = True

    sync_results_to_active_object(context)

    if (
        edit_to_object
        and current_mode == 'OBJECT'
        and settings is not None
        and settings.mode == 'CHECK'
        and settings.show_overlay
    ):
        refresh_meshcheck_results(context)
        return

    if changed_object_names or force_check_scene_dirty:
        invalidate_check_cache(context, edit_cache=False)
        invalidate_preview_cache(context)

    scene[AUTO_REFRESH_SELECTION_KEY] = _get_selected_mesh_signature(context)
    current_object, _active_object = _get_active_mesh_name(context)
    scene[ACTIVE_CHECK_OBJECT_KEY] = current_object
    scene[ACTIVE_CHECK_SIGNATURE_KEY] = _get_active_check_signature(context)


def _meshcheck_needs_depsgraph_handler(context):
    scene = getattr(context, "scene", None) if context is not None else None
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return False

    if settings.mode == 'CHECK' and settings.show_overlay:
        return True

    return bool(settings.preview_results or settings.check_results)


def register_depsgraph_handler():
    if on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)


def unregister_depsgraph_handler():
    if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)

    EDIT_TOPOLOGY_SIGNATURE_CACHE.clear()
    EDIT_SHAPE_SIGNATURE_CACHE.clear()


def sync_depsgraph_handler_state(context=None):
    if context is None:
        context = bpy.context

    if _meshcheck_needs_depsgraph_handler(context):
        register_depsgraph_handler()
        if _should_check_edit_geometry_signature(context):
            active_name, active_object = _get_active_mesh_name(context)
            if active_name and active_object is not None:
                _prime_active_edit_mesh_check_signature(active_object)
    else:
        unregister_depsgraph_handler()


@bpy.app.handlers.persistent
def on_exit_pre(dummy=None):
    del dummy
    context = bpy.context
    scene = getattr(context, "scene", None)
    if not _scene_needs_cleanup(scene):
        return

    if scene is not None:
        settings = getattr(scene, "yl_omnihud_meshcheck", None)
        if settings is not None:
            scene[PREVIEW_LIST_SYNC_KEY] = True
            scene[CHECK_LIST_SYNC_KEY] = True
            clear_preview_results(context)
            clear_check_results(context)
            settings.mode = 'PREVIEW'
            settings.scope = 'VISIBLE'
            settings.show_overlay = False
            settings.check_use_xray = False
            if PREVIEW_LIST_SYNC_KEY in scene:
                del scene[PREVIEW_LIST_SYNC_KEY]
            if CHECK_LIST_SYNC_KEY in scene:
                del scene[CHECK_LIST_SYNC_KEY]
        _clear_scene_runtime_keys(scene)
    RUNTIME_CACHE["scope_objects"].clear()
    RUNTIME_CACHE["preview_result_states"].clear()
    RUNTIME_CACHE["check_result_states"].clear()
    RUNTIME_CACHE["dirty_preview_objects"].clear()
    RUNTIME_CACHE["dirty_check_objects"].clear()
    invalidate_preview_cache()
    invalidate_check_cache()


@bpy.app.handlers.persistent
def on_save_pre(dummy=None):
    del dummy
    SAVE_RUNTIME_STATE_SNAPSHOT.clear()

    for scene in bpy.data.scenes:
        pointer = _scene_pointer(scene)
        if not pointer:
            continue
        snapshot = {
            key: scene[key]
            for key in SCENE_RUNTIME_KEYS
            if key in scene
        }
        if snapshot:
            SAVE_RUNTIME_STATE_SNAPSHOT[pointer] = snapshot
            _clear_scene_runtime_keys(scene)


@bpy.app.handlers.persistent
def on_save_post(dummy=None):
    del dummy
    for scene in bpy.data.scenes:
        pointer = _scene_pointer(scene)
        snapshot = SAVE_RUNTIME_STATE_SNAPSHOT.get(pointer)
        if not snapshot:
            continue
        for key, value in snapshot.items():
            scene[key] = value
    SAVE_RUNTIME_STATE_SNAPSHOT.clear()


@bpy.app.handlers.persistent
def on_depsgraph_update(scene=None, depsgraph=None):
    context = bpy.context
    if context is None:
        return

    scene = getattr(context, "scene", None)
    if scene is None:
        return
    settings = getattr(scene, "yl_omnihud_meshcheck", None)
    current_mode = getattr(context, "mode", "")

    previous_mode = scene.get(PREVIOUS_CONTEXT_MODE_KEY, "")
    scene[PREVIOUS_CONTEXT_MODE_KEY] = current_mode
    edit_to_object = (
        previous_mode == 'EDIT_MESH'
        and current_mode == 'OBJECT'
        and settings is not None
        and settings.mode == 'CHECK'
        and settings.show_overlay
    )
    object_to_edit = (
        previous_mode == 'OBJECT'
        and current_mode == 'EDIT_MESH'
        and settings is not None
        and settings.mode == 'CHECK'
        and settings.show_overlay
    )

    force_check_scene_dirty = False
    changed_object_names = set()
    has_mesh_geometry_update = _depsgraph_has_mesh_geometry_update(depsgraph)

    if object_to_edit:
        refresh_edit_mode_active_check_overlay(context)

    if has_mesh_geometry_update and current_mode == 'EDIT_MESH':
        active_name, active_object = _get_active_mesh_name(context)
        if active_name and active_object is not None:
            if _should_check_edit_geometry_signature(context):
                edit_geometry_changed = _has_active_edit_mesh_check_refresh_changed(active_object)
            else:
                edit_geometry_changed = _has_active_edit_topology_changed(active_object)
            if edit_geometry_changed:
                changed_object_names.add(active_name)
    elif has_mesh_geometry_update:
        if _can_scan_depsgraph_now():
            changed_object_names = _collect_depsgraph_changed_mesh_objects(context, depsgraph)
        else:
            force_check_scene_dirty = True

    if changed_object_names:
        for object_name in changed_object_names:
            invalidate_geometry_memos(object_name)
        mark_runtime_objects_dirty(changed_object_names, preview=True, check=True)
        scene[CHECK_SCENE_DIRTY_KEY] = True

    if current_mode == 'EDIT_MESH':
        _refresh_edit_overlay_from_depsgraph(context, changed_object_names)
        return

    if not (has_mesh_geometry_update or edit_to_object or force_check_scene_dirty):
        sync_results_to_active_object(context)
        sync_depsgraph_handler_state(context)
        return

    _process_object_mode_depsgraph_update(
        context,
        changed_object_names,
        edit_to_object=edit_to_object,
        force_check_scene_dirty=force_check_scene_dirty,
    )
    sync_depsgraph_handler_state(context)


def register_handlers():
    global DRAW_HANDLER_VIEW

    if DRAW_HANDLER_VIEW is None:
        DRAW_HANDLER_VIEW = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_view,
            (),
            "WINDOW",
            "POST_VIEW",
        )

    cleanup_handlers = _cleanup_handlers()
    if cleanup_handlers is not None and on_exit_pre not in cleanup_handlers:
        cleanup_handlers.append(on_exit_pre)
    if on_save_pre not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(on_save_pre)
    if on_save_post not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(on_save_post)

    sync_depsgraph_handler_state()


def unregister_handlers():
    global DRAW_HANDLER_VIEW

    if DRAW_HANDLER_VIEW is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER_VIEW, "WINDOW")
        DRAW_HANDLER_VIEW = None

    cleanup_handlers = _cleanup_handlers()
    if cleanup_handlers is not None and on_exit_pre in cleanup_handlers:
        cleanup_handlers.remove(on_exit_pre)
    if on_save_pre in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(on_save_pre)
    if on_save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_save_post)
    SAVE_RUNTIME_STATE_SNAPSHOT.clear()

    unregister_depsgraph_handler()
    EDIT_SHAPE_SIGNATURE_CACHE.clear()

    invalidate_preview_cache()
    invalidate_check_cache()
