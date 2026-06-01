from .geometry import OBJECT_MEMOS


PREVIEW_LIST_SYNC_KEY = "_yl_meshcheck_preview_list_sync"
CHECK_LIST_SYNC_KEY = "_yl_meshcheck_check_list_sync"
OWNER_AREA_KEY = "_yl_meshcheck_owner_area"
RUNNING_PREVIEW_KEY = "_yl_meshcheck_running_preview"
RUNNING_CHECK_KEY = "_yl_meshcheck_running_check"
ACTIVE_OBJECT_SYNC_KEY = "_yl_meshcheck_active_object_sync"
PREVIEW_REFRESH_SIGNATURE_KEY = "_yl_meshcheck_preview_refresh_signature"
CHECK_REFRESH_SIGNATURE_KEY = "_yl_meshcheck_check_refresh_signature"
CHECK_SCENE_DIRTY_KEY = "_yl_meshcheck_check_scene_dirty"

CHECK_CACHE = {
    "object_name": "",
    "matrix_signature": None,
    "prefs_signature": None,
    "data": None,
    "dirty": True,
    "version": 0,
    "edit_object_name": "",
    "edit_matrix_signature": None,
    "edit_prefs_signature": None,
    "edit_data": None,
    "edit_dirty": True,
    "edit_version": 0,
    "edit_quick_signature": (),
}

RUNTIME_CACHE = {
    "scope_objects": {},
    "preview_result_states": {},
    "check_result_states": {},
    "dirty_preview_objects": set(),
    "dirty_check_objects": set(),
}


def invalidate_geometry_memos(object_name=None):
    if object_name is None:
        OBJECT_MEMOS.clear()
        RUNTIME_CACHE["scope_objects"].clear()
        return
    OBJECT_MEMOS.pop(object_name, None)


def _tag_view3d_redraw(context):
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


def set_meshcheck_owner(context):
    scene = getattr(context, "scene", None)
    area = getattr(context, "area", None)
    if scene is None or area is None or getattr(area, "type", None) != "VIEW_3D":
        return
    try:
        scene[OWNER_AREA_KEY] = str(area.as_pointer())
    except ReferenceError:
        return


def is_meshcheck_owner_context(context):
    scene = getattr(context, "scene", None)
    area = getattr(context, "area", None)
    if scene is None or area is None:
        return False

    owner_area = str(scene.get(OWNER_AREA_KEY, ""))
    if not owner_area:
        return True

    return str(area.as_pointer()) == owner_area


def invalidate_preview_cache(context=None):
    if context is not None:
        _tag_view3d_redraw(context)


def tag_check_redraw(context=None):
    if context is not None:
        _tag_view3d_redraw(context)


def invalidate_check_cache(context=None, *, object_cache=True, edit_cache=True):
    if object_cache:
        CHECK_CACHE["object_name"] = ""
        CHECK_CACHE["matrix_signature"] = None
        CHECK_CACHE["prefs_signature"] = None
        CHECK_CACHE["data"] = None
        CHECK_CACHE["dirty"] = True
    if edit_cache:
        CHECK_CACHE["edit_object_name"] = ""
        CHECK_CACHE["edit_matrix_signature"] = None
        CHECK_CACHE["edit_prefs_signature"] = None
        CHECK_CACHE["edit_data"] = None
        CHECK_CACHE["edit_dirty"] = True
        CHECK_CACHE["edit_quick_signature"] = ()
    tag_check_redraw(context)


def _empty_overlay_payload():
    return {
        "ngon_faces": [],
        "double_points": [],
        "long_tri_segments": [],
        "long_tri_faces": [],
        "tiny_face_points": [],
        "tiny_face_faces": [],
        "pole_points": [],
        "isolated_points": [],
        "non_manifold_segments": [],
        "missing_sharp_segments": [],
    }


def _store_check_overlay_cache(object_name, matrix_signature, prefs_signature, data):
    CHECK_CACHE["version"] += 1
    if data is not None:
        data["_batch_signature"] = (
            "object",
            object_name,
            matrix_signature,
            prefs_signature,
            CHECK_CACHE["version"],
        )
    CHECK_CACHE["object_name"] = object_name
    CHECK_CACHE["matrix_signature"] = matrix_signature
    CHECK_CACHE["prefs_signature"] = prefs_signature
    CHECK_CACHE["data"] = data
    CHECK_CACHE["dirty"] = False


def _store_edit_check_overlay_cache(object_name, matrix_signature, prefs_signature, data):
    CHECK_CACHE["edit_version"] += 1
    if data is not None:
        data["_batch_signature"] = (
            "edit",
            object_name,
            matrix_signature,
            prefs_signature,
            CHECK_CACHE["edit_version"],
        )
    CHECK_CACHE["edit_object_name"] = object_name
    CHECK_CACHE["edit_matrix_signature"] = matrix_signature
    CHECK_CACHE["edit_prefs_signature"] = prefs_signature
    CHECK_CACHE["edit_data"] = data
    CHECK_CACHE["edit_dirty"] = False


def _safe_visible_get(obj):
    try:
        return bool(obj.visible_get())
    except Exception:
        return False


def _scope_cache_signature(context, scope):
    scene = getattr(context, "scene", None)
    if scene is None:
        return ()

    view_layer = getattr(context, "view_layer", None)
    objects = getattr(view_layer, "objects", []) if view_layer is not None else []
    entries = []
    for obj in objects:
        if getattr(obj, "type", None) != 'MESH' or getattr(obj, "data", None) is None:
            continue
        entries.append((obj.name, int(_safe_visible_get(obj)), getattr(obj, "hide_select", False)))

    entries.sort(key=lambda item: item[0])

    selected_signature = ()
    if scope == 'SELECTED':
        selected_mesh_names = sorted(
            obj.name
            for obj in getattr(context, "selected_objects", [])
            if getattr(obj, "type", None) == 'MESH' and getattr(obj, "data", None) is not None
        )
        selected_signature = tuple(selected_mesh_names)

    return (scope, tuple(entries), selected_signature)


def _get_cached_scope_object_names(context, scope):
    cache = RUNTIME_CACHE["scope_objects"]
    entry = cache.get(scope)
    if entry is None:
        return None

    signature = entry.get("signature")
    if signature != _scope_cache_signature(context, scope):
        cache.pop(scope, None)
        return None
    return list(entry.get("names", ()))


def _store_cached_scope_object_names(context, scope, objects):
    RUNTIME_CACHE["scope_objects"][scope] = {
        "signature": _scope_cache_signature(context, scope),
        "names": [obj.name for obj in objects],
    }


def _preview_result_states(scene):
    del scene
    return dict(RUNTIME_CACHE["preview_result_states"])


def _check_result_states(scene):
    del scene
    return dict(RUNTIME_CACHE["check_result_states"])


def _store_preview_result_states(scene, states):
    del scene
    RUNTIME_CACHE["preview_result_states"] = dict(states)


def _store_check_result_states(scene, states):
    del scene
    RUNTIME_CACHE["check_result_states"] = dict(states)


def mark_runtime_objects_dirty(object_names, preview=False, check=False):
    if not object_names:
        return
    if preview:
        RUNTIME_CACHE["dirty_preview_objects"].update(object_names)
    if check:
        RUNTIME_CACHE["dirty_check_objects"].update(object_names)


def consume_runtime_dirty_objects(mode):
    key = "dirty_preview_objects" if mode == "preview" else "dirty_check_objects"
    names = set(RUNTIME_CACHE[key])
    RUNTIME_CACHE[key].clear()
    return names
