import bpy
from .draw import draw_callback_view
from .core.results import (
    clear_check_results,
    clear_preview_results,
    has_refresh_signature_changed,
    refresh_active_check_result,
    refresh_edit_mode_active_check_result,
    sync_results_to_active_object,
)
from .core.runtime import (
    ACTIVE_OBJECT_SYNC_KEY,
    CHECK_CACHE,
    CHECK_SCENE_DIRTY_KEY,
    CHECK_LIST_SYNC_KEY,
    RUNTIME_CACHE,
    CHECK_REFRESH_SIGNATURE_KEY,
    invalidate_geometry_memos,
    invalidate_check_cache,
    invalidate_preview_cache,
    mark_runtime_objects_dirty,
    PREVIEW_REFRESH_SIGNATURE_KEY,
    PREVIEW_LIST_SYNC_KEY,
)
from .operators import refresh_meshcheck_results
from .properties import _restore_viewport_overlay_state
from ..heatmap.logic import is_heatmap_active
from ..overlay.core import get_prefs


DRAW_HANDLER_VIEW = None
AUTO_REFRESH_TIMER_INTERVAL = 0.15
AUTO_REFRESH_PENDING_KEY = "_yl_meshcheck_auto_refresh_pending"
AUTO_REFRESH_SELECTION_KEY = "_yl_meshcheck_auto_refresh_selection"
SCENE_REFRESH_TIMER_INTERVAL = 0.08
ACTIVE_CHECK_REFRESH_INTERVAL = 0.01
EDIT_MODE_REALTIME_TRI_LIMIT_DEFAULT = 25000
ACTIVE_CHECK_PENDING_KEY = "_yl_meshcheck_active_check_pending"
ACTIVE_CHECK_SIGNATURE_KEY = "_yl_meshcheck_active_check_signature"
ACTIVE_CHECK_OBJECT_KEY = "_yl_meshcheck_active_check_object"
PREVIOUS_CONTEXT_MODE_KEY = "_yl_meshcheck_previous_context_mode"


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


def _should_auto_refresh(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or settings.scope != 'SELECTED':
        return False

    if settings.mode == 'CHECK' and getattr(context, "mode", "") == 'EDIT_MESH':
        return False

    if settings.mode == 'PREVIEW':
        return bool(settings.preview_results)
    return bool(settings.check_results)


def _run_debounced_refresh():
    context = bpy.context
    scene = getattr(context, "scene", None) if context is not None else None
    if context is None or scene is None:
        return None

    if not scene.get(AUTO_REFRESH_PENDING_KEY):
        return None

    scene[AUTO_REFRESH_PENDING_KEY] = False
    refresh_meshcheck_results(context)
    scene[AUTO_REFRESH_SELECTION_KEY] = _get_selected_mesh_signature(context)
    return None


def _schedule_auto_refresh(context):
    scene = getattr(context, "scene", None)
    if scene is None or not _should_auto_refresh(context):
        return

    scene[AUTO_REFRESH_PENDING_KEY] = True
    if not bpy.app.timers.is_registered(_run_debounced_refresh):
        bpy.app.timers.register(_run_debounced_refresh, first_interval=AUTO_REFRESH_TIMER_INTERVAL)


def _run_scene_refresh():
    context = bpy.context
    scene = getattr(context, "scene", None) if context is not None else None
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if context is None or scene is None or settings is None:
        return None

    # In edit mode, keep the active-object overlay responsive but defer the
    # expensive full result-list rebuild until the user exits edit mode.
    if settings.mode == 'CHECK' and getattr(context, "mode", "") == 'EDIT_MESH':
        return None

    keep_polling = False
    needs_refresh = False
    if settings.mode == 'PREVIEW' and settings.preview_results and is_heatmap_active(context):
        keep_polling = True
        needs_refresh = has_refresh_signature_changed(context, mode="preview")
    elif settings.mode == 'CHECK' and settings.show_overlay and settings.check_results:
        keep_polling = True
        needs_refresh = bool(scene.get(CHECK_SCENE_DIRTY_KEY)) or has_refresh_signature_changed(context, mode="check")

    if needs_refresh:
        refresh_meshcheck_results(context)
    return SCENE_REFRESH_TIMER_INTERVAL if keep_polling else None


def ensure_scene_refresh_timer():
    if not bpy.app.timers.is_registered(_run_scene_refresh):
        bpy.app.timers.register(_run_scene_refresh, first_interval=SCENE_REFRESH_TIMER_INTERVAL)


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


def _run_active_check_refresh():
    context = bpy.context
    scene = getattr(context, "scene", None) if context is not None else None
    if context is None or scene is None:
        return None

    if not scene.get(ACTIVE_CHECK_PENDING_KEY):
        return None

    _refresh_active_check_now(context)
    return None


def _schedule_active_check_refresh(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return

    active_name = ""
    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if active_object is not None and getattr(active_object, "type", None) == 'MESH':
        active_name = active_object.name

    scene[ACTIVE_CHECK_OBJECT_KEY] = active_name
    scene[ACTIVE_CHECK_PENDING_KEY] = True
    if not bpy.app.timers.is_registered(_run_active_check_refresh):
        bpy.app.timers.register(_run_active_check_refresh, first_interval=ACTIVE_CHECK_REFRESH_INTERVAL)


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


def _refresh_active_check_now(context):
    scene = getattr(context, "scene", None)
    if scene is not None:
        scene[ACTIVE_CHECK_PENDING_KEY] = False

    if getattr(context, "mode", "") == 'EDIT_MESH':
        refresh_edit_mode_active_check_result(context)
    else:
        refresh_active_check_result(context)

    if scene is not None:
        active_name, _active_object = _get_active_mesh_name(context)
        scene[ACTIVE_CHECK_OBJECT_KEY] = active_name
        scene[ACTIVE_CHECK_SIGNATURE_KEY] = _get_active_check_signature(context)


@bpy.app.handlers.persistent
def on_file_load(dummy):
    del dummy
    context = bpy.context
    _restore_viewport_overlay_state(context)
    scene = getattr(context, "scene", None)
    if scene is not None:
        settings = getattr(scene, "yl_omnihud_meshcheck", None)
        if settings is not None:
            clear_preview_results(context)
            clear_check_results(context)
            scene[PREVIEW_LIST_SYNC_KEY] = True
            scene[CHECK_LIST_SYNC_KEY] = True
            try:
                settings.mode = 'PREVIEW'
                settings.scope = 'VISIBLE'
                settings.show_overlay = False
                settings.check_use_xray = False
            finally:
                if PREVIEW_LIST_SYNC_KEY in scene:
                    del scene[PREVIEW_LIST_SYNC_KEY]
                if CHECK_LIST_SYNC_KEY in scene:
                    del scene[CHECK_LIST_SYNC_KEY]
        if ACTIVE_OBJECT_SYNC_KEY in scene:
            del scene[ACTIVE_OBJECT_SYNC_KEY]
        if AUTO_REFRESH_SELECTION_KEY in scene:
            del scene[AUTO_REFRESH_SELECTION_KEY]
        if AUTO_REFRESH_PENDING_KEY in scene:
            del scene[AUTO_REFRESH_PENDING_KEY]
        if ACTIVE_CHECK_PENDING_KEY in scene:
            del scene[ACTIVE_CHECK_PENDING_KEY]
        if ACTIVE_CHECK_SIGNATURE_KEY in scene:
            del scene[ACTIVE_CHECK_SIGNATURE_KEY]
        if ACTIVE_CHECK_OBJECT_KEY in scene:
            del scene[ACTIVE_CHECK_OBJECT_KEY]
        if PREVIEW_REFRESH_SIGNATURE_KEY in scene:
            del scene[PREVIEW_REFRESH_SIGNATURE_KEY]
        if CHECK_REFRESH_SIGNATURE_KEY in scene:
            del scene[CHECK_REFRESH_SIGNATURE_KEY]
        if CHECK_SCENE_DIRTY_KEY in scene:
            del scene[CHECK_SCENE_DIRTY_KEY]
    RUNTIME_CACHE["scope_objects"].clear()
    RUNTIME_CACHE["preview_result_states"].clear()
    RUNTIME_CACHE["check_result_states"].clear()
    RUNTIME_CACHE["dirty_preview_objects"].clear()
    RUNTIME_CACHE["dirty_check_objects"].clear()
    invalidate_preview_cache()
    invalidate_check_cache()


@bpy.app.handlers.persistent
def on_depsgraph_update(scene=None, depsgraph=None):
    context = bpy.context
    if context is None:
        return

    sync_results_to_active_object(context)
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    settings = getattr(scene, "yl_omnihud_meshcheck", None)
    current_mode = getattr(context, "mode", "")
    previous_mode = scene.get(PREVIOUS_CONTEXT_MODE_KEY, "")
    scene[PREVIOUS_CONTEXT_MODE_KEY] = current_mode

    if (
        previous_mode == 'EDIT_MESH'
        and current_mode == 'OBJECT'
        and settings is not None
        and settings.mode == 'CHECK'
        and settings.show_overlay
    ):
        refresh_meshcheck_results(context)
        return

    if depsgraph is not None:
        changed_object_names = set()
        for update in depsgraph.updates:
            update_id = getattr(update, "id", None)
            if isinstance(update_id, bpy.types.Object):
                if (
                    getattr(update_id, "type", None) == 'MESH'
                    and getattr(update_id, "data", None) is not None
                    and bool(getattr(update, "is_updated_geometry", False))
                ):
                    changed_object_names.add(update_id.name)
                continue
            if isinstance(update_id, bpy.types.Mesh):
                for obj in getattr(context.view_layer, "objects", []):
                    if getattr(obj, "type", None) != 'MESH' or getattr(obj, "data", None) is None:
                        continue
                    if obj.data == update_id:
                        changed_object_names.add(obj.name)

        if changed_object_names:
            for object_name in changed_object_names:
                invalidate_geometry_memos(object_name)
            mark_runtime_objects_dirty(changed_object_names, preview=True, check=True)
            scene[CHECK_SCENE_DIRTY_KEY] = True
    else:
        changed_object_names = set()

    active_check_signature = _get_active_check_signature(context)
    if active_check_signature:
        previous_signature = scene.get(ACTIVE_CHECK_SIGNATURE_KEY, "")
        previous_object = scene.get(ACTIVE_CHECK_OBJECT_KEY, "")
        current_object, _active_object = _get_active_mesh_name(context)
        scene[ACTIVE_CHECK_SIGNATURE_KEY] = active_check_signature
        scene[ACTIVE_CHECK_OBJECT_KEY] = current_object
        if getattr(context, "mode", "") == 'EDIT_MESH':
            if current_object and current_object in changed_object_names:
                if _should_refresh_edit_mode_active_check_realtime(context):
                    _refresh_active_check_now(context)
                else:
                    _schedule_active_check_refresh(context)
        elif previous_object == current_object and previous_signature != active_check_signature:
            if not CHECK_CACHE.get("dirty", True):
                _schedule_active_check_refresh(context)

    selection_signature = _get_selected_mesh_signature(context)
    if scene.get(AUTO_REFRESH_SELECTION_KEY, "") == selection_signature:
        if settings is None:
            return
        has_scene_results = bool(settings.preview_results) if settings.mode == 'PREVIEW' else bool(settings.check_results)
        skip_scene_refresh = settings.mode == 'CHECK' and getattr(context, "mode", "") == 'EDIT_MESH'
        if has_scene_results and not skip_scene_refresh and not bpy.app.timers.is_registered(_run_scene_refresh):
            bpy.app.timers.register(_run_scene_refresh, first_interval=SCENE_REFRESH_TIMER_INTERVAL)
        return

    scene[AUTO_REFRESH_SELECTION_KEY] = selection_signature
    _schedule_auto_refresh(context)
    if settings is not None:
        has_scene_results = bool(settings.preview_results) if settings.mode == 'PREVIEW' else bool(settings.check_results)
        skip_scene_refresh = settings.mode == 'CHECK' and getattr(context, "mode", "") == 'EDIT_MESH'
        if has_scene_results and not skip_scene_refresh and not bpy.app.timers.is_registered(_run_scene_refresh):
            bpy.app.timers.register(_run_scene_refresh, first_interval=SCENE_REFRESH_TIMER_INTERVAL)


def register_handlers():
    global DRAW_HANDLER_VIEW

    if DRAW_HANDLER_VIEW is None:
        DRAW_HANDLER_VIEW = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_view,
            (),
            "WINDOW",
            "POST_VIEW",
        )

    if on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load)

    if on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)


def unregister_handlers():
    global DRAW_HANDLER_VIEW

    if bpy.app.timers.is_registered(_run_debounced_refresh):
        bpy.app.timers.unregister(_run_debounced_refresh)
    if bpy.app.timers.is_registered(_run_scene_refresh):
        bpy.app.timers.unregister(_run_scene_refresh)
    if bpy.app.timers.is_registered(_run_active_check_refresh):
        bpy.app.timers.unregister(_run_active_check_refresh)

    if DRAW_HANDLER_VIEW is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER_VIEW, "WINDOW")
        DRAW_HANDLER_VIEW = None

    if on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load)

    if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)

    invalidate_preview_cache()
    invalidate_check_cache()
