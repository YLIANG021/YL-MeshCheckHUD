import json
from math import log1p

import bpy
from mathutils import Color

from ..mesh_metrics import get_evaluated_object_triangle_count


COLOR_KEY = "_yl_heatmap_original_color"
MARK_KEY = "_yl_heatmap_active"
SHADING_TYPE_KEY = "_yl_heatmap_prev_shading_type"
SHADING_COLOR_KEY = "_yl_heatmap_prev_color_type"
ACTIVE_SCOPE_KEY = "_yl_heatmap_active_scope"
SORTED_OBJECT_NAMES_KEY = "_yl_heatmap_sorted_object_names"
FOCUS_INDEX_KEY = "_yl_heatmap_focus_index"
REFRESH_SIGNATURE_KEY = "_yl_heatmap_refresh_signature"
COMPLEXITY_VALUES_KEY = "_yl_heatmap_complexity_values"
COMPLEXITY_TOTAL_KEY = "_yl_heatmap_complexity_total"
OBJECT_STATE_KEY = "_yl_heatmap_object_states"
SCOPE_OBJECT_NAMES_KEY = "_yl_heatmap_scope_object_names"
OWNER_AREA_KEY = "_yl_heatmap_owner_area"
OWNER_REGION_KEY = "_yl_heatmap_owner_region"
VIEWPORT_DISPLAY_STATE_KEY = "_yl_heatmap_viewport_display_states"
MARKED_OBJECT_NAMES_KEY = "_yl_heatmap_marked_object_names"
ACTIVE_SCENE_POINTERS = set()


def _scene_pointer(scene):
    if scene is None:
        return 0
    return int(scene.as_pointer())


def _get_view3d_shading(context):
    space = getattr(context, "space_data", None)
    if not space or space.type != 'VIEW_3D':
        return None
    return getattr(space, "shading", None)


def _iter_view3d_shadings(context):
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return

    for window in window_manager.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = next((space for space in area.spaces if space.type == "VIEW_3D"), None)
            shading = getattr(space, "shading", None) if space is not None else None
            if space is None or shading is None:
                continue
            yield space, shading


def _load_viewport_display_states(scene):
    raw = scene.get(VIEWPORT_DISPLAY_STATE_KEY, "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _store_viewport_display_states(scene, states):
    if states:
        scene[VIEWPORT_DISPLAY_STATE_KEY] = json.dumps(states)
    elif VIEWPORT_DISPLAY_STATE_KEY in scene:
        del scene[VIEWPORT_DISPLAY_STATE_KEY]


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


def _safe_object_name(obj):
    try:
        return getattr(obj, "name", "")
    except ReferenceError:
        return ""


def _safe_is_mesh_object(obj):
    if obj is None:
        return False
    try:
        return getattr(obj, "type", None) == 'MESH' and getattr(obj, "data", None) is not None
    except ReferenceError:
        return False


def _safe_visible_get(obj):
    try:
        return bool(obj.visible_get())
    except Exception:
        return False


def iter_mesh_objects(context, scope='ALL'):
    if scope == 'SELECTED':
        source = context.selected_objects
    elif scope == 'VISIBLE':
        source = [obj for obj in context.view_layer.objects if _safe_visible_get(obj)]
    else:
        source = context.view_layer.objects

    return [obj for obj in source if _safe_is_mesh_object(obj)]


def iter_marked_mesh_objects(context):
    objects = []
    for obj in context.view_layer.objects:
        if not _safe_is_mesh_object(obj):
            continue
        try:
            marked = obj.get(MARK_KEY)
        except ReferenceError:
            continue
        if marked:
            objects.append(obj)
    return objects


def get_complexity_value(obj, depsgraph=None):
    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except (AttributeError, ReferenceError, RuntimeError):
            depsgraph = None

    if depsgraph is None:
        return 0
    return get_evaluated_object_triangle_count(obj, depsgraph)


def get_stored_complexity_value(context, obj):
    if obj is None:
        return 0

    values = context.scene.get(COMPLEXITY_VALUES_KEY) or {}
    if obj.name in values:
        return int(values[obj.name])

    return get_complexity_value(obj)


def _resolve_preview_owner_targets(context):
    scene = getattr(context, "scene", None)
    area = getattr(context, "area", None)
    if scene is None or area is None:
        return None, None

    if area.type != 'VIEW_3D':
        return None, None

    window_region = next((item for item in area.regions if item.type == 'WINDOW'), None)
    if window_region is None:
        return None, None

    return area, window_region


def set_preview_owner(context):
    scene = getattr(context, "scene", None)
    area, region = _resolve_preview_owner_targets(context)
    if scene is None or area is None or region is None:
        return

    scene[OWNER_AREA_KEY] = str(area.as_pointer())
    scene[OWNER_REGION_KEY] = str(region.as_pointer())


def is_preview_owner_context(context):
    scene = getattr(context, "scene", None)
    area = getattr(context, "area", None)
    region = getattr(context, "region", None)
    if scene is None or area is None or region is None:
        return False

    owner_area = str(scene.get(OWNER_AREA_KEY, ""))
    owner_region = str(scene.get(OWNER_REGION_KEY, ""))
    if not owner_area:
        return True

    if str(area.as_pointer()) != owner_area:
        return False
    if owner_region and str(region.as_pointer()) != owner_region:
        return False
    return True


def _store_original_color(obj):
    if COLOR_KEY not in obj:
        obj[COLOR_KEY] = list(obj.color)


def _restore_original_color(obj):
    if COLOR_KEY in obj:
        try:
            obj.color = tuple(obj[COLOR_KEY])
        except Exception:
            obj.color = (1.0, 1.0, 1.0, 1.0)
        del obj[COLOR_KEY]

    if MARK_KEY in obj:
        del obj[MARK_KEY]


def _restore_marked_object_display(obj):
    if COLOR_KEY in obj:
        try:
            obj.color = tuple(obj[COLOR_KEY])
        except Exception:
            obj.color = (1.0, 1.0, 1.0, 1.0)


def _clear_scene_preview_state(scene):
    for key in (
        ACTIVE_SCOPE_KEY,
        SORTED_OBJECT_NAMES_KEY,
        FOCUS_INDEX_KEY,
        REFRESH_SIGNATURE_KEY,
        COMPLEXITY_VALUES_KEY,
        COMPLEXITY_TOTAL_KEY,
        OBJECT_STATE_KEY,
        SCOPE_OBJECT_NAMES_KEY,
        OWNER_AREA_KEY,
        OWNER_REGION_KEY,
        MARKED_OBJECT_NAMES_KEY,
    ):
        if key in scene:
            del scene[key]


def scene_needs_cleanup(scene):
    if scene is None:
        return False

    scene_keys = (
        ACTIVE_SCOPE_KEY,
        SORTED_OBJECT_NAMES_KEY,
        FOCUS_INDEX_KEY,
        REFRESH_SIGNATURE_KEY,
        COMPLEXITY_VALUES_KEY,
        COMPLEXITY_TOTAL_KEY,
        OBJECT_STATE_KEY,
        SCOPE_OBJECT_NAMES_KEY,
        OWNER_AREA_KEY,
        OWNER_REGION_KEY,
        SHADING_TYPE_KEY,
        SHADING_COLOR_KEY,
        VIEWPORT_DISPLAY_STATE_KEY,
        MARKED_OBJECT_NAMES_KEY,
    )
    if any(key in scene for key in scene_keys):
        return True

    return any(
        getattr(obj, "type", None) == 'MESH'
        and (MARK_KEY in obj or COLOR_KEY in obj)
        for obj in scene.objects
    )


def _iter_stored_marked_mesh_objects(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return []

    seen_names = set()
    objects = []

    for name in scene.get(MARKED_OBJECT_NAMES_KEY) or []:
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        obj = bpy.data.objects.get(name)
        if _safe_is_mesh_object(obj):
            objects.append(obj)

    for obj in iter_marked_mesh_objects(context):
        obj_name = _safe_object_name(obj)
        if not obj_name or obj_name in seen_names:
            continue
        seen_names.add(obj_name)
        objects.append(obj)

    for obj in scene.objects:
        obj_name = _safe_object_name(obj)
        if not obj_name or not _safe_is_mesh_object(obj) or obj_name in seen_names:
            continue
        if MARK_KEY not in obj and COLOR_KEY not in obj:
            continue
        seen_names.add(obj_name)
        objects.append(obj)

    return objects


def _enable_object_color_display(context):
    scene = context.scene
    states = _load_viewport_display_states(scene)
    changed = False

    for space, shading in _iter_view3d_shadings(context):
        space_key = str(space.as_pointer())
        if space_key not in states:
            states[space_key] = {
                "type": shading.type,
                "color_type": shading.color_type,
            }
            changed = True
        shading.type = 'SOLID'
        shading.color_type = 'OBJECT'

    if changed:
        _store_viewport_display_states(scene, states)


def _restore_viewport_display(context):
    scene = context.scene
    states = _load_viewport_display_states(scene)
    restored_any = False

    for space, shading in _iter_view3d_shadings(context):
        state = states.get(str(space.as_pointer()))
        if state is None:
            continue
        prev_type = state.get("type")
        prev_color = state.get("color_type")
        if prev_type:
            try:
                shading.type = prev_type
                restored_any = True
            except Exception:
                pass
        if prev_color:
            try:
                shading.color_type = prev_color
                restored_any = True
            except Exception:
                pass

    _store_viewport_display_states(scene, {})

    if restored_any:
        if SHADING_TYPE_KEY in scene:
            del scene[SHADING_TYPE_KEY]
        if SHADING_COLOR_KEY in scene:
            del scene[SHADING_COLOR_KEY]
        return

    shading = _get_view3d_shading(context)
    if not shading:
        return

    prev_type = scene.get(SHADING_TYPE_KEY)
    prev_color = scene.get(SHADING_COLOR_KEY)

    if prev_type:
        try:
            shading.type = prev_type
        except Exception:
            pass
        del scene[SHADING_TYPE_KEY]

    if prev_color:
        try:
            shading.color_type = prev_color
        except Exception:
            pass
        del scene[SHADING_COLOR_KEY]


def _normalize_logarithmic(value, min_value, max_value):
    if max_value <= min_value:
        return 0.5

    low = log1p(max(0, min_value))
    high = log1p(max(0, max_value))
    if high <= low:
        return 0.5

    ratio = (log1p(max(0, value)) - low) / (high - low)
    return max(0.0, min(ratio, 1.0))


def _color_from_ratio(ratio, low_hue=0.66, high_hue=0.0):
    hue = low_hue + (high_hue - low_hue) * ratio
    color = Color()
    color.hsv = (hue, 1.0, 1.0)
    return (color.r, color.g, color.b, 1.0)


def _get_material_uv_signature(obj, mesh):
    if mesh is None:
        return (), 0, 0

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

    try:
        material_slot_count = len(getattr(obj, "material_slots", ()))
    except Exception:
        material_slot_count = 0

    return material_signature, material_slot_count, uv_count


def _get_object_state(obj, depsgraph=None):
    try:
        is_visible = bool(obj.visible_get())
    except Exception:
        is_visible = False

    mesh = getattr(obj, "data", None)
    mesh_key = int(mesh.as_pointer()) if mesh is not None else 0
    try:
        vert_count = len(getattr(mesh, "vertices", ()))
        edge_count = len(getattr(mesh, "edges", ()))
        poly_count = len(getattr(mesh, "polygons", ()))
    except Exception:
        vert_count = 0
        edge_count = 0
        poly_count = 0

    try:
        evaluated_tris = int(get_evaluated_object_triangle_count(obj, depsgraph))
    except Exception:
        evaluated_tris = 0

    material_signature, material_slot_count, uv_count = _get_material_uv_signature(obj, mesh)

    return "|".join(
        (
            str(int(obj.as_pointer())),
            str(mesh_key),
            str(int(is_visible)),
            str(vert_count),
            str(edge_count),
            str(poly_count),
            str(evaluated_tris),
            repr(material_signature),
            str(material_slot_count),
            str(uv_count),
        )
    )


def _build_scope_snapshot(context, scope):
    depsgraph = None
    try:
        depsgraph = context.evaluated_depsgraph_get()
    except (AttributeError, ReferenceError, RuntimeError):
        depsgraph = None
    objects = iter_mesh_objects(context, scope=scope)
    states = {obj.name: _get_object_state(obj, depsgraph=depsgraph) for obj in objects}
    return objects, states


def _build_signature_from_states(states):
    return "\n".join(f"{name}:{states[name]}" for name in sorted(states))


def _get_preview_refresh_signature(context, scope=None):
    if context is None or getattr(context, "scene", None) is None:
        return ""

    if scope is None:
        scope = context.scene.get(ACTIVE_SCOPE_KEY) or getattr(
            getattr(context.scene, "yl_omnihud_heatmap", None),
            "scope",
            "ALL",
        )

    _objects, states = _build_scope_snapshot(context, scope)
    return _build_signature_from_states(states)


def get_stored_preview_refresh_signature(scene):
    return scene.get(REFRESH_SIGNATURE_KEY, "")


def has_preview_refresh_signature_changed(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return False
    return _get_preview_refresh_signature(context) != get_stored_preview_refresh_signature(scene)


def get_sorted_preview_objects(context):
    names = context.scene.get(SORTED_OBJECT_NAMES_KEY) or []
    objects = []
    for name in names:
        obj = context.view_layer.objects.get(name)
        try:
            marked = obj.get(MARK_KEY) if _safe_is_mesh_object(obj) else False
        except ReferenceError:
            marked = False
        if marked:
            objects.append(obj)
    return objects


def get_focus_index(context):
    objects = get_sorted_preview_objects(context)
    if not objects:
        return 0
    raw_index = int(context.scene.get(FOCUS_INDEX_KEY, 0))
    return max(0, min(raw_index, len(objects) - 1))


def get_focused_object(context):
    objects = get_sorted_preview_objects(context)
    if not objects:
        return None
    return objects[get_focus_index(context)]


def get_focused_object_rank(context):
    objects = get_sorted_preview_objects(context)
    if not objects:
        return 0, 0
    index = get_focus_index(context)
    return index + 1, len(objects)


def get_focused_object_ratio(context):
    objects = get_sorted_preview_objects(context)
    focused = get_focused_object(context)
    if not objects or focused is None:
        return 0.0

    total = int(context.scene.get(COMPLEXITY_TOTAL_KEY, 0))
    if total <= 0:
        total = sum(get_stored_complexity_value(context, obj) for obj in objects)
    if total <= 0:
        return 0.0
    return get_stored_complexity_value(context, focused) / total


def set_focus_index(context, index):
    objects = get_sorted_preview_objects(context)
    if not objects:
        return False

    clamped_index = max(0, min(int(index), len(objects) - 1))
    if get_focus_index(context) == clamped_index:
        return True

    context.scene[FOCUS_INDEX_KEY] = clamped_index
    _tag_view3d_redraw(context)
    return True


def set_focus_object_name(context, object_name):
    if not object_name:
        return False

    objects = get_sorted_preview_objects(context)
    if not objects:
        return False

    for index, obj in enumerate(objects):
        if obj.name == object_name:
            return set_focus_index(context, index)
    return False


def sync_focused_object_selection(context):
    if context.mode != 'OBJECT':
        return False

    focused = get_focused_object(context)
    view_layer = getattr(context, "view_layer", None)
    if focused is None or view_layer is None:
        return False

    for obj in view_layer.objects:
        if obj.select_get():
            obj.select_set(False)

    focused.select_set(True)
    view_layer.objects.active = focused
    return True


def is_heatmap_active(context, scope=None):
    scene = getattr(context, "scene", None)
    if scene is None:
        return False
    if _scene_pointer(scene) not in ACTIVE_SCENE_POINTERS:
        return False
    active_scope = scene.get(ACTIVE_SCOPE_KEY)
    if not active_scope:
        return False
    if scope is not None and active_scope != scope:
        return False
    return any(True for obj in iter_marked_mesh_objects(context))


def _restore_removed_targets(context, current_names):
    for obj in _iter_stored_marked_mesh_objects(context):
        if obj.name not in current_names:
            _restore_original_color(obj)


def apply_heatmap(context, scope='ALL', precomputed_values=None, preserve_focus=False, force_rebuild=False):
    objects, current_states = _build_scope_snapshot(context, scope)
    if not objects:
        clear_heatmap(context)
        return 0

    scene = context.scene
    previous_values = scene.get(COMPLEXITY_VALUES_KEY) or {}
    previous_states = scene.get(OBJECT_STATE_KEY) or {}
    previous_focus_name = ""
    if preserve_focus:
        previous_focus = get_focused_object(context)
        previous_focus_name = previous_focus.name if previous_focus is not None else ""

    current_names = {obj.name for obj in objects}
    _restore_removed_targets(context, current_names)

    depsgraph = None
    if precomputed_values is None:
        try:
            depsgraph = context.evaluated_depsgraph_get()
        except (AttributeError, ReferenceError, RuntimeError):
            depsgraph = None

    values = []
    min_value = None
    max_value = 0
    total_value = 0
    complexity_map = {}

    for obj in objects:
        if precomputed_values is not None and obj.name in precomputed_values:
            value = int(precomputed_values[obj.name])
        elif (
            not force_rebuild
            and previous_states.get(obj.name) == current_states[obj.name]
            and obj.name in previous_values
        ):
            value = int(previous_values[obj.name])
        else:
            value = get_complexity_value(obj, depsgraph=depsgraph)

        complexity_map[obj.name] = value
        values.append((obj, value))
        total_value += value
        if min_value is None or value < min_value:
            min_value = value
        if value > max_value:
            max_value = value

    values.sort(key=lambda item: item[1], reverse=True)

    _enable_object_color_display(context)
    scene[ACTIVE_SCOPE_KEY] = scope
    ACTIVE_SCENE_POINTERS.add(_scene_pointer(scene))
    sorted_names = [obj.name for obj, _value in values]
    scene[SORTED_OBJECT_NAMES_KEY] = sorted_names
    if preserve_focus and previous_focus_name in sorted_names:
        scene[FOCUS_INDEX_KEY] = sorted_names.index(previous_focus_name)
    else:
        scene[FOCUS_INDEX_KEY] = 0
    scene[COMPLEXITY_VALUES_KEY] = complexity_map
    scene[COMPLEXITY_TOTAL_KEY] = total_value
    scene[OBJECT_STATE_KEY] = current_states
    scene[SCOPE_OBJECT_NAMES_KEY] = sorted(current_names)
    scene[MARKED_OBJECT_NAMES_KEY] = sorted_names

    for obj, value in values:
        _store_original_color(obj)
        obj[MARK_KEY] = True
        ratio = _normalize_logarithmic(value, min_value if min_value is not None else 0, max_value)
        obj.color = _color_from_ratio(ratio)

    scene[REFRESH_SIGNATURE_KEY] = _build_signature_from_states(current_states)
    _tag_view3d_redraw(context)
    from .handlers import sync_heatmap_update_timer_state

    sync_heatmap_update_timer_state(context)
    return len(values)


def clear_heatmap(context, scope=None):
    del scope
    targets = _iter_stored_marked_mesh_objects(context)
    for obj in targets:
        _restore_original_color(obj)

    _clear_scene_preview_state(context.scene)
    ACTIVE_SCENE_POINTERS.discard(_scene_pointer(context.scene))
    _restore_viewport_display(context)
    _tag_view3d_redraw(context)
    from .handlers import sync_heatmap_update_timer_state

    sync_heatmap_update_timer_state(context)


def refresh_heatmap(context):
    settings = getattr(context.scene, "yl_omnihud_heatmap", None)
    if settings is None or not is_heatmap_active(context):
        return

    from ..meshcheck.core import run_preview

    meshcheck_settings = getattr(context.scene, "yl_omnihud_meshcheck", None)
    active_preview_index = getattr(meshcheck_settings, "active_preview_index", None)
    run_preview(context, active_index_override=active_preview_index)
    scope = settings.scope
    apply_heatmap(context, scope=scope, preserve_focus=True)


def sync_heatmap_display_for_mode(context):
    if context is None or not is_heatmap_active(context):
        return False

    mode = getattr(context, "mode", "")

    if mode == 'EDIT_MESH':
        clear_heatmap(context)
        return True

    return False
