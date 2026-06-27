import bpy

from ...heatmap.logic import is_heatmap_active, set_focus_object_name
from ...mesh_metrics import get_evaluated_object_triangle_count
from .config import (
    _get_check_settings_signature,
    _meshcheck_settings_from_context,
    get_enabled_check_ids,
    get_visible_check_ids,
)
from .geometry import _get_mesh_object_state_signature, _get_preview_object_state_signature, get_geometry_memo
from .overlay import (
    _active_mesh_object,
    _build_edit_mode_overlay_payload,
    _get_matrix_signature,
    get_active_check_overlay_data as _get_active_check_overlay_data,
    get_edit_mode_active_check_overlay_data,
)
from .runtime import (
    ACTIVE_OBJECT_SYNC_KEY,
    CHECK_LIST_SYNC_KEY,
    CHECK_REFRESH_SIGNATURE_KEY,
    CHECK_SCENE_DIRTY_KEY,
    PREVIEW_LIST_SYNC_KEY,
    PREVIEW_REFRESH_SIGNATURE_KEY,
    RUNNING_CHECK_KEY,
    RUNNING_PREVIEW_KEY,
    RUNTIME_CACHE,
    _check_result_states,
    _get_cached_scope_object_names,
    _preview_result_states,
    _safe_visible_get,
    _store_cached_scope_object_names,
    _store_check_result_states,
    _store_edit_check_overlay_cache,
    _store_preview_result_states,
    _tag_view3d_redraw,
    consume_runtime_dirty_objects,
    invalidate_check_cache,
    invalidate_geometry_memos,
    invalidate_preview_cache,
    tag_check_redraw,
)


def _sync_meshcheck_depsgraph_handler(context):
    from ..handlers import sync_depsgraph_handler_state

    sync_depsgraph_handler_state(context)


def _iter_mesh_objects(context, scope):
    view_layer = getattr(context, "view_layer", None)
    if view_layer is None:
        return []

    cached_names = _get_cached_scope_object_names(context, scope)
    if cached_names is not None:
        objects = []
        for name in cached_names:
            obj = view_layer.objects.get(name)
            if obj is not None and getattr(obj, "type", None) == 'MESH' and getattr(obj, "data", None) is not None:
                objects.append(obj)
        return objects

    if scope == 'SELECTED':
        source = getattr(context, "selected_objects", [])
    elif scope == 'VISIBLE':
        source = [obj for obj in view_layer.objects if _safe_visible_get(obj)]
    else:
        source = view_layer.objects

    objects = [
        obj for obj in source
        if getattr(obj, "type", None) == 'MESH' and getattr(obj, "data", None) is not None
    ]
    _store_cached_scope_object_names(context, scope, objects)
    return objects


def _get_check_inputs_signature(context, settings=None):
    if settings is None:
        settings = _meshcheck_settings_from_context(context)
    return (
        tuple(get_enabled_check_ids(settings)),
        _get_check_settings_signature(context),
    )


def _get_check_result_state_signature(context, obj, check_inputs_signature=None):
    if check_inputs_signature is None:
        check_inputs_signature = _get_check_inputs_signature(context)
    return (
        _get_mesh_object_state_signature(obj),
        check_inputs_signature,
    )


def _get_meshcheck_refresh_signature(context, scope, mode="preview"):
    depsgraph = None
    if mode == "preview":
        try:
            depsgraph = context.evaluated_depsgraph_get()
        except (AttributeError, ReferenceError, RuntimeError):
            depsgraph = None
    else:
        check_inputs_signature = _get_check_inputs_signature(context)
    entries = []
    for obj in _iter_mesh_objects(context, scope):
        try:
            is_visible = bool(obj.visible_get())
        except Exception:
            is_visible = False
        if mode == "preview":
            state_signature = _get_preview_object_state_signature(obj, depsgraph)
        else:
            state_signature = _get_check_result_state_signature(
                context,
                obj,
                check_inputs_signature,
            )
        entries.append((obj.name, int(is_visible), state_signature))

    entries.sort(key=lambda item: item[0])
    return "\n".join(repr(item) for item in entries)


def format_material_slot_value(item):
    material_count = int(getattr(item, "material_count", 0))
    slot_count = int(getattr(item, "material_slot_count", material_count))
    if slot_count <= 0 and material_count > 0:
        slot_count = material_count
    if material_count == slot_count:
        return str(material_count)
    return f"{material_count}/{slot_count}"


def get_stored_refresh_signature(scene, mode):
    if scene is None:
        return ""
    key = PREVIEW_REFRESH_SIGNATURE_KEY if mode == "preview" else CHECK_REFRESH_SIGNATURE_KEY
    return scene.get(key, "")


def has_refresh_signature_changed(context, mode="preview"):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if scene is None or settings is None:
        return False
    scope = settings.scope
    return _get_meshcheck_refresh_signature(context, scope, mode=mode) != get_stored_refresh_signature(scene, mode)


def _preview_result(context, obj, depsgraph):
    del context
    mesh = getattr(obj, "data", None)
    material_count = 0
    material_slot_count = 0
    uv_count = 0
    if mesh is not None:
        try:
            material_count = len(
                {
                    int(material.as_pointer())
                    for material in getattr(mesh, "materials", ())
                    if material is not None
                }
            )
        except Exception:
            material_count = 0
        try:
            material_slot_count = len(getattr(obj, "material_slots", ()))
        except Exception:
            material_slot_count = 0
        try:
            uv_count = len(getattr(mesh, "uv_layers", ()))
        except Exception:
            uv_count = 0
    return {
        "object_name": obj.name,
        "tris": get_evaluated_object_triangle_count(obj, depsgraph),
        "material_count": material_count,
        "material_slot_count": material_slot_count,
        "uv_count": uv_count,
        "ratio": 0.0,
        "findings": 0,
    }


def _check_result(context, obj, depsgraph, detailed=False):
    settings = _meshcheck_settings_from_context(context)
    memo = get_geometry_memo(
        context,
        obj,
        depsgraph=depsgraph,
        rebuild=True,
        enabled_ids=get_enabled_check_ids(settings),
        detailed=detailed,
    )
    if memo is None:
        return {
            "object_name": obj.name,
            "ngon_count": 0,
            "double_vert_count": 0,
            "long_tri_count": 0,
            "tiny_face_count": 0,
            "pole_count": 0,
            "isolated_vert_count": 0,
            "non_manifold_count": 0,
            "missing_sharp_edge_count": 0,
            "has_findings": False,
        }
    return memo.to_result_dict()


def _sync_results_to_settings(context, results, mode="preview", active_index_override=None):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return

    sync_key = PREVIEW_LIST_SYNC_KEY if mode == "preview" else CHECK_LIST_SYNC_KEY
    active_name = ""
    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if active_object is not None:
        active_name = active_object.name
    scene[sync_key] = True
    try:
        target = settings.preview_results if mode == "preview" else settings.check_results
        target.clear()
        for item in results:
            entry = target.add()
            entry.object_name = item["object_name"]
            entry.tris = item.get("tris", 0)
            if mode == "preview":
                entry.material_count = item.get("material_count", 0)
                entry.material_slot_count = item.get("material_slot_count", 0)
                entry.uv_count = item.get("uv_count", 0)
                entry.ratio = item.get("ratio", 0.0)
            else:
                entry.ngon_count = item.get("ngon_count", 0)
                entry.double_vert_count = item.get("double_vert_count", 0)
                entry.long_tri_count = item.get("long_tri_count", 0)
                entry.tiny_face_count = item.get("tiny_face_count", 0)
                entry.pole_count = item.get("pole_count", 0)
                entry.isolated_vert_count = item.get("isolated_vert_count", 0)
                entry.non_manifold_count = item.get("non_manifold_count", 0)
                entry.missing_sharp_edge_count = item.get("missing_sharp_edge_count", 0)
                entry.has_findings = item.get("has_findings", False)
        if active_index_override is not None:
            if target:
                active_index = max(0, min(int(active_index_override), len(target) - 1))
            else:
                active_index = 0
        else:
            active_index = _find_result_index_by_object_name(target, active_name)
        if mode == "preview":
            settings.active_preview_index = active_index if active_index >= 0 else 0
        else:
            settings.active_check_index = active_index if active_index >= 0 else 0
    finally:
        if sync_key in scene:
            del scene[sync_key]


def _preview_item_to_dict(item):
    return {
        "object_name": item.object_name,
        "tris": item.tris,
        "material_count": item.material_count,
        "material_slot_count": item.material_slot_count,
        "uv_count": item.uv_count,
        "ratio": item.ratio,
    }


def _check_item_to_dict(item):
    return {
        "object_name": item.object_name,
        "tris": item.tris,
        "ngon_count": item.ngon_count,
        "double_vert_count": item.double_vert_count,
        "long_tri_count": item.long_tri_count,
        "tiny_face_count": item.tiny_face_count,
        "pole_count": item.pole_count,
        "isolated_vert_count": item.isolated_vert_count,
        "non_manifold_count": item.non_manifold_count,
        "missing_sharp_edge_count": item.missing_sharp_edge_count,
        "has_findings": item.has_findings,
    }


def _find_result_index_by_object_name(results, object_name):
    if not object_name or not results:
        return -1

    for index, item in enumerate(results):
        if item.object_name == object_name:
            return index
    return -1


def _assign_check_result_item(entry, item):
    entry.object_name = item["object_name"]
    entry.tris = item.get("tris", 0)
    entry.ngon_count = item.get("ngon_count", 0)
    entry.double_vert_count = item.get("double_vert_count", 0)
    entry.long_tri_count = item.get("long_tri_count", 0)
    entry.tiny_face_count = item.get("tiny_face_count", 0)
    entry.pole_count = item.get("pole_count", 0)
    entry.isolated_vert_count = item.get("isolated_vert_count", 0)
    entry.non_manifold_count = item.get("non_manifold_count", 0)
    entry.missing_sharp_edge_count = item.get("missing_sharp_edge_count", 0)
    entry.has_findings = item.get("has_findings", False)


def _get_preview_sort_value(item, sort_by):
    if sort_by == 'TRIS':
        return item["tris"]
    if sort_by == 'MATS':
        return (item["material_count"], item.get("material_slot_count", item["material_count"]))
    if sort_by == 'UVS':
        return item["uv_count"]
    if sort_by == 'RATIO':
        return item["ratio"]
    return item["object_name"].lower()


def _get_check_sort_value(item, sort_by):
    if sort_by == 'NGONS':
        return item["ngon_count"]
    if sort_by == 'DOUBLES':
        return item["double_vert_count"]
    if sort_by == 'LONG_TRIS':
        return item["long_tri_count"]
    if sort_by == 'TINY_FACES':
        return item["tiny_face_count"]
    if sort_by == 'POLES':
        return item["pole_count"]
    if sort_by == 'ISOLATED_VERTS':
        return item["isolated_vert_count"]
    if sort_by == 'NON_MANIFOLD':
        return item["non_manifold_count"]
    if sort_by == 'MISSING_SHARP':
        return item["missing_sharp_edge_count"]
    if sort_by == 'NAME':
        return item["object_name"].lower()
    return int(item["has_findings"])


def _sort_preview_results(results, settings):
    sort_by = settings.preview_sort_by
    reverse = settings.preview_sort_descending
    if sort_by == 'NAME':
        results.sort(key=lambda item: item["object_name"].lower(), reverse=reverse)
    else:
        results.sort(
            key=lambda item: (
                _get_preview_sort_value(item, sort_by),
                item["tris"],
                item["object_name"].lower(),
            ),
            reverse=reverse,
        )


def _sort_check_results(results, settings):
    sort_by = settings.check_sort_by
    reverse = settings.check_sort_descending
    if sort_by == 'NAME':
        results.sort(key=lambda item: item["object_name"].lower(), reverse=reverse)
    else:
        results.sort(
            key=lambda item: (
                _get_check_sort_value(item, sort_by),
                item["object_name"].lower(),
            ),
            reverse=reverse,
        )


def sort_existing_preview_results(context, activate_first=False):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or not settings.preview_results:
        return False

    results = [_preview_item_to_dict(item) for item in settings.preview_results]
    _sort_preview_results(results, settings)
    _sync_results_to_settings(
        context,
        results,
        mode="preview",
        active_index_override=0 if activate_first else None,
    )
    invalidate_preview_cache(context)
    return True


def sort_existing_check_results(context, activate_first=False):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or not settings.check_results:
        return False

    results = [_check_item_to_dict(item) for item in settings.check_results]
    _sort_check_results(results, settings)
    _sync_results_to_settings(
        context,
        results,
        mode="check",
        active_index_override=0 if activate_first else None,
    )
    tag_check_redraw(context)
    return True


def get_active_preview_object_name(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or not settings.preview_results:
        return ""
    index = settings.active_preview_index
    if index < 0 or index >= len(settings.preview_results):
        return ""
    return settings.preview_results[index].object_name


def get_active_check_object_name(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return ""
    if not settings.check_results:
        if settings.mode == 'CHECK' and settings.show_overlay:
            active_object = _active_mesh_object(context)
            return active_object.name if active_object is not None else ""
        return ""
    index = settings.active_check_index
    if index < 0 or index >= len(settings.check_results):
        return ""
    return settings.check_results[index].object_name


def _select_object_by_name(context, object_name, preserve_selection=False):
    if not object_name or getattr(context, "mode", None) != 'OBJECT':
        return False

    view_layer = getattr(context, "view_layer", None)
    if view_layer is None:
        return False

    obj = view_layer.objects.get(object_name)
    if obj is None:
        return False

    if not preserve_selection:
        for other in view_layer.objects:
            if other.select_get():
                other.select_set(False)

    obj.select_set(True)
    view_layer.objects.active = obj
    _tag_view3d_redraw(context)
    return True


def sync_active_preview_selection(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    preserve_selection = bool(settings is not None and settings.scope == 'SELECTED')
    return _select_object_by_name(
        context,
        get_active_preview_object_name(context),
        preserve_selection=preserve_selection,
    )


def sync_preview_focus(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or not is_heatmap_active(context):
        return False

    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    active_name = active_object.name if active_object is not None and getattr(active_object, "type", None) == 'MESH' else ""

    if active_name:
        preview_index = _find_result_index_by_object_name(settings.preview_results, active_name)
        if preview_index >= 0:
            scene[PREVIEW_LIST_SYNC_KEY] = True
            try:
                settings.active_preview_index = preview_index
            finally:
                if PREVIEW_LIST_SYNC_KEY in scene:
                    del scene[PREVIEW_LIST_SYNC_KEY]
            return set_focus_object_name(context, active_name)

    return set_focus_object_name(context, get_active_preview_object_name(context))


def sync_active_check_selection(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    preserve_selection = bool(settings is not None and settings.scope == 'SELECTED')
    selected = _select_object_by_name(
        context,
        get_active_check_object_name(context),
        preserve_selection=preserve_selection,
    )
    tag_check_redraw(context)
    return selected


def sync_results_to_active_object(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if settings is None:
        return False

    active_name = active_object.name if active_object is not None and getattr(active_object, "type", None) == 'MESH' else ""
    if scene.get(ACTIVE_OBJECT_SYNC_KEY, "") == active_name:
        return False
    scene[ACTIVE_OBJECT_SYNC_KEY] = active_name

    if not active_name or (not settings.preview_results and not settings.check_results):
        return False

    changed = False
    preview_index = _find_result_index_by_object_name(settings.preview_results, active_name)
    if preview_index >= 0 and preview_index != settings.active_preview_index:
        scene[PREVIEW_LIST_SYNC_KEY] = True
        try:
            settings.active_preview_index = preview_index
        finally:
            if PREVIEW_LIST_SYNC_KEY in scene:
                del scene[PREVIEW_LIST_SYNC_KEY]
        if is_heatmap_active(context):
            set_focus_object_name(context, active_name)
        invalidate_preview_cache(context)
        changed = True

    check_index = _find_result_index_by_object_name(settings.check_results, active_name)
    if check_index >= 0 and check_index != settings.active_check_index:
        scene[CHECK_LIST_SYNC_KEY] = True
        try:
            settings.active_check_index = check_index
        finally:
            if CHECK_LIST_SYNC_KEY in scene:
                del scene[CHECK_LIST_SYNC_KEY]
        tag_check_redraw(context)
        changed = True

    return changed


def get_active_check_overlay_data(context):
    return _get_active_check_overlay_data(context, get_active_check_object_name)


def can_reuse_check_results(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if scene is None or settings is None or not settings.check_results:
        return False
    if bool(scene.get(CHECK_SCENE_DIRTY_KEY)):
        return False
    return not has_refresh_signature_changed(context, mode="check")


def refresh_active_check_result(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or settings.mode != 'CHECK' or not settings.show_overlay or not settings.check_results:
        return False

    active_object = _active_mesh_object(context)
    if active_object is None:
        return False

    active_name = active_object.name
    if _find_result_index_by_object_name(settings.check_results, active_name) < 0:
        return False

    try:
        depsgraph = context.evaluated_depsgraph_get()
    except (AttributeError, ReferenceError, RuntimeError):
        return False

    invalidate_geometry_memos(active_name)
    updated_item = _check_result(context, active_object, depsgraph)

    results = [_check_item_to_dict(item) for item in settings.check_results]
    replaced = False
    for index, item in enumerate(results):
        if item["object_name"] == active_name:
            results[index] = updated_item
            replaced = True
            break

    if not replaced:
        return False

    _sort_check_results(results, settings)
    _sync_results_to_settings(context, results, mode="check")
    scene[CHECK_REFRESH_SIGNATURE_KEY] = _get_meshcheck_refresh_signature(context, settings.scope, mode="check")
    invalidate_check_cache(context)
    return True


def refresh_edit_mode_active_check_overlay(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or settings.mode != 'CHECK' or not settings.show_overlay:
        return False

    active_object = _active_mesh_object(context)
    if active_object is None or not getattr(getattr(active_object, "data", None), "is_editmode", False):
        return False

    visible_ids = get_visible_check_ids(settings)
    matrix_signature = _get_matrix_signature(active_object.matrix_world)
    prefs_signature = ",".join(visible_ids)
    payload = _build_edit_mode_overlay_payload(context, active_object, visible_ids) if visible_ids else None

    _store_edit_check_overlay_cache(active_object.name, matrix_signature, prefs_signature, payload)
    _tag_view3d_redraw(context)
    return True


def refresh_edit_mode_active_check_result(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or settings.mode != 'CHECK' or not settings.show_overlay:
        return False

    active_object = _active_mesh_object(context)
    if active_object is None or not getattr(getattr(active_object, "data", None), "is_editmode", False):
        return False

    active_name = active_object.name
    visible_ids = get_visible_check_ids(settings)
    matrix_signature = _get_matrix_signature(active_object.matrix_world)
    prefs_signature = ",".join(visible_ids)
    payload = _build_edit_mode_overlay_payload(context, active_object, visible_ids) if visible_ids else None

    result_index = _find_result_index_by_object_name(settings.check_results, active_name)
    if result_index >= 0:
        invalidate_geometry_memos(active_name)
        updated_item = _check_result(context, active_object, None, detailed=False)
        _assign_check_result_item(settings.check_results[result_index], updated_item)
        if result_index != settings.active_check_index:
            scene[CHECK_LIST_SYNC_KEY] = True
            try:
                settings.active_check_index = result_index
            finally:
                if CHECK_LIST_SYNC_KEY in scene:
                    del scene[CHECK_LIST_SYNC_KEY]
    else:
        invalidate_geometry_memos(active_name)
        updated_item = _check_result(context, active_object, None, detailed=False)
        scene[CHECK_LIST_SYNC_KEY] = True
        try:
            entry = settings.check_results.add()
            _assign_check_result_item(entry, updated_item)
            settings.active_check_index = len(settings.check_results) - 1
        finally:
            if CHECK_LIST_SYNC_KEY in scene:
                del scene[CHECK_LIST_SYNC_KEY]

    _store_edit_check_overlay_cache(active_name, matrix_signature, prefs_signature, payload)
    _tag_view3d_redraw(context)
    return True


def clear_preview_results(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return
    scene[PREVIEW_LIST_SYNC_KEY] = True
    try:
        settings.preview_results.clear()
        settings.active_preview_index = 0
        invalidate_preview_cache()
    finally:
        if PREVIEW_LIST_SYNC_KEY in scene:
            del scene[PREVIEW_LIST_SYNC_KEY]
    if scene is not None and PREVIEW_REFRESH_SIGNATURE_KEY in scene:
        del scene[PREVIEW_REFRESH_SIGNATURE_KEY]
    RUNTIME_CACHE["preview_result_states"].clear()
    RUNTIME_CACHE["dirty_preview_objects"].clear()
    _sync_meshcheck_depsgraph_handler(context)


def clear_check_results(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return
    scene[CHECK_LIST_SYNC_KEY] = True
    try:
        settings.check_results.clear()
        settings.active_check_index = 0
        invalidate_check_cache()
    finally:
        if CHECK_LIST_SYNC_KEY in scene:
            del scene[CHECK_LIST_SYNC_KEY]
    if scene is not None and CHECK_REFRESH_SIGNATURE_KEY in scene:
        del scene[CHECK_REFRESH_SIGNATURE_KEY]
    if scene is not None and CHECK_SCENE_DIRTY_KEY in scene:
        del scene[CHECK_SCENE_DIRTY_KEY]
    RUNTIME_CACHE["check_result_states"].clear()
    RUNTIME_CACHE["dirty_check_objects"].clear()
    _sync_meshcheck_depsgraph_handler(context)


def _build_preview_results_incremental(context, depsgraph, objects, previous_results, previous_states, dirty_object_names=None):
    results = []
    new_states = {}
    total_tris = 0
    dirty_object_names = dirty_object_names or set()

    for obj in objects:
        state_signature = _get_preview_object_state_signature(obj, depsgraph)
        new_states[obj.name] = state_signature
        item = previous_results.get(obj.name)
        if (
            item is None
            or previous_states.get(obj.name) != state_signature
            or obj.name in dirty_object_names
        ):
            item = _preview_result(context, obj, depsgraph)
        else:
            item = dict(item)
        total_tris += item["tris"]
        results.append(item)

    if total_tris > 0:
        for item in results:
            item["ratio"] = item["tris"] / total_tris
    else:
        for item in results:
            item["ratio"] = 0.0

    return results, new_states


def _build_check_results_incremental(
    context,
    depsgraph,
    objects,
    previous_results,
    previous_states,
    dirty_object_names=None,
):
    results = []
    new_states = {}
    dirty_object_names = dirty_object_names or set()
    check_inputs_signature = _get_check_inputs_signature(context)

    for obj in objects:
        state_signature = _get_check_result_state_signature(
            context,
            obj,
            check_inputs_signature,
        )
        new_states[obj.name] = state_signature
        item = previous_results.get(obj.name)
        if (
            item is None
            or previous_states.get(obj.name) != state_signature
            or obj.name in dirty_object_names
        ):
            item = _check_result(context, obj, depsgraph, detailed=False)
        else:
            item = dict(item)
        results.append(item)

    return results, new_states


def run_preview(context, active_index_override=None):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return 0, 0

    try:
        depsgraph = context.evaluated_depsgraph_get()
    except (AttributeError, ReferenceError, RuntimeError):
        clear_preview_results(context)
        return 0, 0

    scene[RUNNING_PREVIEW_KEY] = True
    invalidate_preview_cache(context)

    try:
        objects = _iter_mesh_objects(context, settings.scope)
        previous_results = {
            item.object_name: _preview_item_to_dict(item)
            for item in settings.preview_results
        }
        previous_states = _preview_result_states(scene)
        dirty_object_names = consume_runtime_dirty_objects("preview")
        results, result_states = _build_preview_results_incremental(
            context,
            depsgraph,
            objects,
            previous_results,
            previous_states,
            dirty_object_names=dirty_object_names,
        )

        _sort_preview_results(results, settings)
        _sync_results_to_settings(
            context,
            results,
            mode="preview",
            active_index_override=active_index_override,
        )
        _store_preview_result_states(scene, result_states)
        scene[PREVIEW_REFRESH_SIGNATURE_KEY] = _get_meshcheck_refresh_signature(context, settings.scope, mode="preview")
        invalidate_preview_cache(context)
        _sync_meshcheck_depsgraph_handler(context)
        return len(objects), len(results)
    finally:
        if RUNNING_PREVIEW_KEY in scene:
            del scene[RUNNING_PREVIEW_KEY]


def run_check(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None:
        return 0, 0

    try:
        depsgraph = context.evaluated_depsgraph_get()
    except (AttributeError, ReferenceError, RuntimeError):
        clear_check_results(context)
        return 0, 0

    scene[RUNNING_CHECK_KEY] = True
    invalidate_check_cache(context)

    try:
        objects = _iter_mesh_objects(context, settings.scope)
        previous_results = {
            item.object_name: _check_item_to_dict(item)
            for item in settings.check_results
        }
        previous_states = _check_result_states(scene)
        dirty_object_names = consume_runtime_dirty_objects("check")
        results, result_states = _build_check_results_incremental(
            context,
            depsgraph,
            objects,
            previous_results,
            previous_states,
            dirty_object_names=dirty_object_names,
        )

        _sort_check_results(results, settings)
        _sync_results_to_settings(context, results, mode="check")
        _store_check_result_states(scene, result_states)
        scene[CHECK_REFRESH_SIGNATURE_KEY] = _get_meshcheck_refresh_signature(context, settings.scope, mode="check")
        scene[CHECK_SCENE_DIRTY_KEY] = False
        invalidate_check_cache(context)
        _sync_meshcheck_depsgraph_handler(context)
        return len(objects), sum(1 for item in results if item["has_findings"])
    finally:
        if RUNNING_CHECK_KEY in scene:
            del scene[RUNNING_CHECK_KEY]
