import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from .definitions import CHECK_DEFINITIONS
from .core.results import (
    can_reuse_check_results,
    clear_check_results,
    clear_preview_results,
    refresh_edit_mode_active_check_result,
    run_check,
    run_preview,
    sort_existing_check_results,
    sync_active_check_selection,
    sync_active_preview_selection,
    sync_preview_focus,
)
from .operators import schedule_deferred_check_refresh
from .core.runtime import (
    CHECK_LIST_SYNC_KEY,
    invalidate_check_cache,
    invalidate_preview_cache,
    PREVIEW_LIST_SYNC_KEY,
    set_meshcheck_owner,
    tag_check_redraw,
)
from ..heatmap.logic import (
    apply_heatmap,
    clear_heatmap,
    is_heatmap_active,
    set_focus_object_name,
    set_preview_owner,
)
from ..overlay.core import get_prefs


EDIT_MODE_REALTIME_TRI_LIMIT_DEFAULT = 25000


def _is_syncing(context):
    if context is None:
        return True
    scene = getattr(context, "scene", None)
    if scene is None:
        return True
    return bool(scene.get(PREVIEW_LIST_SYNC_KEY) or scene.get(CHECK_LIST_SYNC_KEY))


def _restore_viewport_overlay_state(context):
    del context


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


def _get_cached_active_tri_count(settings, active_name):
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
    if context is None:
        return 0

    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if active_object is None or getattr(active_object, "type", None) != 'MESH':
        return 0

    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    cached_tri_count = _get_cached_active_tri_count(settings, active_object.name)
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

    return max(0, poly_count * 2)


def _should_refresh_edit_mode_check_realtime(context):
    return _estimate_active_mesh_triangle_count(context) <= _get_edit_mode_realtime_tri_limit()


def _ensure_scene_refresh_timer():
    from .handlers import ensure_scene_refresh_timer

    ensure_scene_refresh_timer()


def _update_scope(self, context):
    if _is_syncing(context):
        return
    if self.mode == 'PREVIEW':
        checked_count, _ranked_count = run_preview(context)
        if is_heatmap_active(context):
            heatmap_settings = getattr(context.scene, "yl_omnihud_heatmap", None)
            if heatmap_settings is not None:
                heatmap_settings.scope = self.scope
            if checked_count > 0:
                apply_heatmap(context, scope=self.scope)
                sync_preview_focus(context)
                _ensure_scene_refresh_timer()
            else:
                clear_heatmap(context)
                clear_preview_results(context)
    else:
        checked_count, _problem_count = run_check(context)
        if checked_count == 0:
            clear_check_results(context)
            self.show_overlay = False


def _update_overlay_visibility(self, context):
    if _is_syncing(context):
        return
    invalidate_preview_cache(context)
    tag_check_redraw(context)


def _update_mode(self, context):
    if _is_syncing(context):
        return
    if context is None:
        invalidate_preview_cache(context)
        tag_check_redraw(context)
        return
    if getattr(context, "mode", "") == 'EDIT_MESH' and self.mode == 'PREVIEW':
        invalidate_preview_cache(context)
        tag_check_redraw(context)
        return

    hud_active = is_heatmap_active(context) or self.show_overlay
    if hud_active:
        if self.mode == 'PREVIEW':
            _restore_viewport_overlay_state(context)
            if self.show_overlay:
                self.show_overlay = False
            heatmap_settings = getattr(context.scene, "yl_omnihud_heatmap", None)
            if heatmap_settings is not None:
                heatmap_settings.scope = self.scope
            set_preview_owner(context)

            if self.preview_results and apply_heatmap(context, scope=self.scope) > 0:
                sync_preview_focus(context)
                invalidate_preview_cache(context)
            else:
                checked_count, _ranked_count = run_preview(context)
                if checked_count > 0 and apply_heatmap(context, scope=self.scope) > 0:
                    sync_preview_focus(context)
                    invalidate_preview_cache(context)
                else:
                    clear_heatmap(context)
                    clear_preview_results(context)
        else:
            if is_heatmap_active(context):
                clear_heatmap(context)
            set_meshcheck_owner(context)
            if can_reuse_check_results(context):
                self.show_overlay = True
                sync_active_check_selection(context)
                tag_check_redraw(context)
                _ensure_scene_refresh_timer()
            else:
                checked_count, _problem_count = run_check(context)
                self.show_overlay = checked_count > 0
                if self.show_overlay:
                    _ensure_scene_refresh_timer()
                if checked_count == 0:
                    clear_check_results(context)
    else:
        _restore_viewport_overlay_state(context)
        invalidate_preview_cache(context)
        tag_check_redraw(context)


def _update_preview_sort(self, context):
    if _is_syncing(context):
        return
    invalidate_preview_cache(context)


def _update_check_sort(self, context):
    if _is_syncing(context):
        return
    invalidate_check_cache(context)


def _is_check_sort_visible(settings, sort_by):
    if sort_by == 'NAME':
        return True

    for definition in CHECK_DEFINITIONS:
        if definition["id"] == sort_by:
            return getattr(settings, definition["show_prop"], False)
    return False


def _ensure_valid_check_sort(settings):
    if _is_check_sort_visible(settings, settings.check_sort_by):
        return False

    settings.check_sort_by = 'NAME'
    settings.check_sort_descending = False
    return True


def _update_active_check(self, context):
    if _is_syncing(context):
        return
    tag_check_redraw(context)


def _refresh_check_results_if_needed(settings, context):
    if context is None or getattr(context, "mode", "") == 'EDIT_MESH':
        return
    if settings.mode != 'CHECK':
        return
    if not settings.check_results and not settings.show_overlay:
        return

    schedule_deferred_check_refresh(context)


def _update_check_visibility(self, context):
    if _is_syncing(context):
        return
    if "_enabled_check_ids_snapshot" not in self:
        self["_enabled_check_ids_snapshot"] = ",".join(
            definition["id"]
            for definition in CHECK_DEFINITIONS
            if getattr(self, definition["show_prop"], False)
        )
    current_enabled_ids = {
        definition["id"]
        for definition in CHECK_DEFINITIONS
        if getattr(self, definition["show_prop"], False)
    }
    skip_batched_refresh = self.get("_skip_restore_state_update", False)
    if not skip_batched_refresh:
        self.check_visibility_restore_state = ""
    if _ensure_valid_check_sort(self):
        sort_existing_check_results(context)
    self["_enabled_check_ids_snapshot"] = ",".join(
        definition["id"]
        for definition in CHECK_DEFINITIONS
        if definition["id"] in current_enabled_ids
    )
    if not skip_batched_refresh:
        _refresh_check_results_if_needed(self, context)
    invalidate_check_cache(context)


def _update_check_thresholds(self, context):
    del self
    if _is_syncing(context):
        return
    settings = getattr(getattr(context, "scene", None), "yl_omnihud_meshcheck", None) if context is not None else None
    if settings is not None:
        if (
            context is not None
            and getattr(context, "mode", "") == 'EDIT_MESH'
            and settings.mode == 'CHECK'
            and settings.show_overlay
            and _should_refresh_edit_mode_check_realtime(context)
        ):
            refresh_edit_mode_active_check_result(context)
            return
        _refresh_check_results_if_needed(settings, context)
    invalidate_check_cache(context)


def _get_show_all_checks(self):
    return all(getattr(self, definition["show_prop"], False) for definition in CHECK_DEFINITIONS)


def _set_show_all_checks(self, value):
    enable_all = bool(value)
    enabled_ids = [
        definition["id"]
        for definition in CHECK_DEFINITIONS
        if getattr(self, definition["show_prop"], False)
    ]
    restore_ids = {
        check_id
        for check_id in self.check_visibility_restore_state.split(",")
        if check_id
    }

    self["_skip_restore_state_update"] = True
    try:
        if enable_all:
            if not enabled_ids and not restore_ids:
                restore_ids = {definition["id"] for definition in CHECK_DEFINITIONS}
            target_ids = restore_ids or {definition["id"] for definition in CHECK_DEFINITIONS}
            for definition in CHECK_DEFINITIONS:
                setattr(self, definition["show_prop"], definition["id"] in target_ids)
            self.check_visibility_restore_state = ""
        elif enabled_ids:
            self.check_visibility_restore_state = ",".join(enabled_ids)
            for definition in CHECK_DEFINITIONS:
                setattr(self, definition["show_prop"], False)
    finally:
        self.pop("_skip_restore_state_update", None)

    _refresh_check_results_if_needed(self, bpy.context)


def _update_active_preview_index(self, context):
    if _is_syncing(context):
        return
    if context is not None and is_heatmap_active(context):
        if 0 <= self.active_preview_index < len(self.preview_results):
            set_focus_object_name(context, self.preview_results[self.active_preview_index].object_name)
    sync_active_preview_selection(context)


def _update_active_check_index(self, context):
    del self
    if _is_syncing(context):
        return
    sync_active_check_selection(context)


class YLOMNIHUD_PreviewResultItem(bpy.types.PropertyGroup):
    object_name: StringProperty()
    tris: IntProperty(default=0, min=0)
    material_count: IntProperty(default=0, min=0)
    uv_count: IntProperty(default=0, min=0)
    ratio: FloatProperty(default=0.0, min=0.0, max=1.0)


class YLOMNIHUD_CheckResultItem(bpy.types.PropertyGroup):
    object_name: StringProperty()
    tris: IntProperty(default=0, min=0)
    ngon_count: IntProperty(default=0, min=0)
    double_vert_count: IntProperty(default=0, min=0)
    long_tri_count: IntProperty(default=0, min=0)
    tiny_face_count: IntProperty(default=0, min=0)
    pole_count: IntProperty(default=0, min=0)
    isolated_vert_count: IntProperty(default=0, min=0)
    non_manifold_count: IntProperty(default=0, min=0)
    missing_sharp_edge_count: IntProperty(default=0, min=0)
    has_findings: BoolProperty(default=False)


class YLOMNIHUD_MeshCheckSettings(bpy.types.PropertyGroup):
    mode: EnumProperty(
        name="Mode",
        items=[
            ('PREVIEW', "Heatmap", "Show triangle density ranking"),
            ('CHECK', "Check", "Show mesh issue diagnostics"),
        ],
        default='PREVIEW',
        update=_update_mode,
    )
    scope: EnumProperty(
        name="Scope",
        items=[
            ('VISIBLE', "Visible", "Analyze visible mesh objects only"),
            ('SELECTED', "Selected", "Analyze selected mesh objects only"),
            ('ALL', "All", "Analyze all mesh objects in the current view layer"),
        ],
        default='VISIBLE',
        update=_update_scope,
    )
    show_overlay: BoolProperty(
        name="Show Overlay",
        default=False,
        update=_update_overlay_visibility,
    )
    check_use_xray: BoolProperty(
        name="X-Ray Check Overlay",
        description="Draw check overlay in front of mesh surfaces",
        default=False,
        update=_update_overlay_visibility,
        options={'SKIP_SAVE'},
    )
    show_ngons: BoolProperty(name="Ngons", default=True, update=_update_check_visibility)
    show_doubles: BoolProperty(name="Doubles", default=True, update=_update_check_visibility)
    show_isolated_verts: BoolProperty(name="Isolated", default=True, update=_update_check_visibility)
    show_long_tris: BoolProperty(name="Needle Tris", default=True, update=_update_check_visibility)
    show_tiny_faces: BoolProperty(name="Tiny Faces", default=True, update=_update_check_visibility)
    show_poles: BoolProperty(name="Poles", default=False, update=_update_check_visibility)
    show_non_manifold: BoolProperty(name="Non-manifold", default=False, update=_update_check_visibility)
    show_missing_sharp: BoolProperty(name="Sharp", default=False, update=_update_check_visibility)
    show_all_checks: BoolProperty(name="All Checks", get=_get_show_all_checks, set=_set_show_all_checks)
    check_visibility_restore_state: StringProperty(default="", options={'HIDDEN', 'SKIP_SAVE'})
    show_advanced: BoolProperty(name="Advanced", default=False)
    show_ngons_column: BoolProperty(name="Ngons", default=True)
    show_doubles_column: BoolProperty(name="Doubles", default=True)
    show_isolated_verts_column: BoolProperty(name="Isolated", default=True)
    show_long_tris_column: BoolProperty(name="Needle Tris", default=True)
    show_tiny_faces_column: BoolProperty(name="Tiny Faces", default=True)
    show_poles_column: BoolProperty(name="Poles", default=True)
    show_non_manifold_column: BoolProperty(name="Non-manifold", default=True)
    show_missing_sharp_column: BoolProperty(name="Sharp", default=True)
    doubles_distance: FloatProperty(
        name="Doubles Distance",
        default=0.0001,
        min=1e-9,
        precision=9,
        step=0.1,
        description="Distance threshold used to group vertices as doubles",
        update=_update_check_thresholds,
    )
    long_tri_ratio_threshold: FloatProperty(
        name="Long Triangle Ratio",
        default=14.0,
        min=1.0,
        precision=2,
        step=10,
        description="Longest edge divided by shortest altitude for needle triangles",
        update=_update_check_thresholds,
    )
    tiny_face_area_threshold: FloatProperty(
        name="Tiny Face Area",
        default=1e-5,
        min=0.0,
        precision=8,
        step=0.1,
        description="Faces at or below this area are classified as dust faces",
        update=_update_check_thresholds,
    )
    pole_threshold: IntProperty(
        name="Pole Threshold",
        default=8,
        min=3,
        max=20,
        description="Vertices with more connected edges than this threshold are classified as poles",
        update=_update_check_thresholds,
    )
    missing_sharp_angle: FloatProperty(
        name="Sharp Angle",
        default=90.0,
        min=0.0,
        max=180.0,
        precision=1,
        description="Face angle threshold for sharp edges",
        update=_update_check_thresholds,
    )
    missing_sharp_skip_marked: BoolProperty(
        name="Skip Marked Sharp",
        default=False,
        description="Ignore edges already marked sharp",
        update=_update_check_thresholds,
    )
    preview_sort_by: EnumProperty(
        name="Preview Sort",
        items=[
            ('TRIS', "Tris", "Sort by triangle count"),
            ('RATIO', "Ratio", "Sort by triangle ratio"),
            ('MATS', "Mats", "Sort by material count"),
            ('UVS', "UVs", "Sort by UV map count"),
            ('NAME', "Object", "Sort by object name"),
        ],
        default='TRIS',
        update=_update_preview_sort,
    )
    preview_sort_descending: BoolProperty(name="Descending", default=True, update=_update_preview_sort)
    check_sort_by: EnumProperty(
        name="Check Sort",
        items=[
            ('NGONS', "Ngons", "Sort by ngon count"),
            ('DOUBLES', "Doubles", "Sort by doubles count"),
            ('ISOLATED_VERTS', "Isolated", "Sort by isolated vertex count"),
            ('LONG_TRIS', "Needle Tris", "Sort by needle triangle count"),
            ('TINY_FACES', "Tiny Faces", "Sort by tiny face count"),
            ('POLES', "Poles", "Sort by pole count"),
            ('NON_MANIFOLD', "Non-manifold", "Sort by non-manifold edge count"),
            ('MISSING_SHARP', "Sharp", "Sort by sharp edge count"),
            ('NAME', "Object", "Sort by object name"),
        ],
        default='NGONS',
        update=_update_check_sort,
    )
    check_sort_descending: BoolProperty(name="Descending", default=True, update=_update_check_sort)
    preview_results: CollectionProperty(type=YLOMNIHUD_PreviewResultItem)
    check_results: CollectionProperty(type=YLOMNIHUD_CheckResultItem)
    active_preview_index: IntProperty(default=0, min=0, update=_update_active_preview_index)
    active_check_index: IntProperty(default=0, min=0, update=_update_active_check_index)
