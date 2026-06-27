import bpy

from ..heatmap.logic import apply_heatmap, clear_heatmap, is_heatmap_active, set_preview_owner
from .definitions import CHECK_DEFINITIONS, get_check_definition
from .core.results import (
    can_reuse_check_results,
    clear_check_results,
    clear_preview_results,
    refresh_edit_mode_active_check_result,
    sync_active_check_selection,
    sync_active_preview_selection,
    run_check,
    run_preview,
    sort_existing_check_results,
    sort_existing_preview_results,
    sync_preview_focus,
)
from .core.runtime import tag_check_redraw, set_meshcheck_owner

translate = bpy.app.translations.pgettext_iface


def _sync_meshcheck_depsgraph_handler(context):
    from .handlers import sync_depsgraph_handler_state

    sync_depsgraph_handler_state(context)


def _all_check_visibility_enabled(settings):
    return all(getattr(settings, definition["show_prop"], False) for definition in CHECK_DEFINITIONS)


def _is_sortable_check_column(settings, sort_by):
    if sort_by == 'NAME':
        return True

    definition = get_check_definition(sort_by, fallback=None)
    if definition is None:
        return False
    return getattr(settings, definition["show_prop"], False)


def refresh_meshcheck_results(context):
    settings = getattr(getattr(context, "scene", None), "yl_omnihud_meshcheck", None)
    if settings is None:
        return 0, 0

    scope = settings.scope
    if settings.mode == 'PREVIEW':
        checked_count, ranked_count = run_preview(context)
        if checked_count <= 0:
            clear_preview_results(context)
            if is_heatmap_active(context):
                clear_heatmap(context)
            return 0, 0

        if is_heatmap_active(context):
            heatmap_settings = getattr(context.scene, "yl_omnihud_heatmap", None)
            if heatmap_settings is not None:
                heatmap_settings.scope = scope
            if getattr(getattr(context, "area", None), "type", None) == 'VIEW_3D':
                set_preview_owner(context)
            apply_heatmap(context, scope=scope)
            sync_preview_focus(context)
        return checked_count, ranked_count

    checked_count, problem_count = run_check(context)
    if checked_count <= 0:
        clear_check_results(context)
        if settings.show_overlay:
            settings.show_overlay = False
        _sync_meshcheck_depsgraph_handler(context)
        return 0, 0

    if settings.show_overlay and getattr(getattr(context, "area", None), "type", None) == 'VIEW_3D':
        set_meshcheck_owner(context)
    _sync_meshcheck_depsgraph_handler(context)
    return checked_count, problem_count


def refresh_check_results_if_needed(context):
    scene = getattr(context, "scene", None) if context is not None else None
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if context is None or scene is None or settings is None:
        return

    if settings.mode != 'CHECK':
        return
    if not settings.check_results and not settings.show_overlay:
        return
    if getattr(context, "mode", "") == 'EDIT_MESH':
        return

    checked_count, _problem_count = refresh_meshcheck_results(context)
    if checked_count <= 0:
        settings.show_overlay = False


class YLOMNIHUD_OT_preview_meshcheck(bpy.types.Operator):
    bl_idname = "yl_omnihud.preview_meshcheck"
    bl_label = "Toggle Analysis HUD"
    bl_description = "Enable or disable the current analysis HUD"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.yl_omnihud_meshcheck
        scope = settings.scope

        if settings.mode == 'PREVIEW':
            if getattr(context, "mode", "") != 'OBJECT':
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except (AttributeError, RuntimeError):
                    self.report({'WARNING'}, translate("Heatmap is available in Object Mode only"))
                    return {'CANCELLED'}
            if settings.show_overlay:
                settings.show_overlay = False
            if is_heatmap_active(context):
                clear_heatmap(context)
                _sync_meshcheck_depsgraph_handler(context)
                return {'FINISHED'}

            heatmap_settings = getattr(context.scene, "yl_omnihud_heatmap", None)
            if heatmap_settings is not None:
                heatmap_settings.scope = scope
            checked_count, ranked_count = run_preview(context)
            set_preview_owner(context)
            count = apply_heatmap(context, scope=scope)
            if count == 0:
                clear_preview_results(context)
                self.report({'WARNING'}, translate("No mesh objects found in the current scope"))
                _sync_meshcheck_depsgraph_handler(context)
                return {'CANCELLED'}
            sync_preview_focus(context)
            _sync_meshcheck_depsgraph_handler(context)
            return {'FINISHED'}

        if settings.show_overlay and is_heatmap_active(context):
            settings.show_overlay = False
            clear_heatmap(context)
            _sync_meshcheck_depsgraph_handler(context)
            return {'FINISHED'}

        if settings.show_overlay:
            settings.show_overlay = False
            _sync_meshcheck_depsgraph_handler(context)
            return {'FINISHED'}

        if is_heatmap_active(context):
            clear_heatmap(context)
        set_meshcheck_owner(context)
        settings.show_overlay = True
        tag_check_redraw(context)

        if getattr(context, "mode", "") == 'EDIT_MESH':
            if not refresh_edit_mode_active_check_result(context):
                settings.show_overlay = False
                self.report({'WARNING'}, translate("No mesh objects found in the current scope"))
                _sync_meshcheck_depsgraph_handler(context)
                return {'CANCELLED'}
            _sync_meshcheck_depsgraph_handler(context)
            return {'FINISHED'}

        if can_reuse_check_results(context):
            sync_active_check_selection(context)
            _sync_meshcheck_depsgraph_handler(context)
            return {'FINISHED'}

        checked_count, problem_count = refresh_meshcheck_results(context)
        if checked_count <= 0:
            settings.show_overlay = False
            self.report({'WARNING'}, translate("No mesh objects found in the current scope"))
            _sync_meshcheck_depsgraph_handler(context)
            return {'CANCELLED'}

        _sync_meshcheck_depsgraph_handler(context)
        return {'FINISHED'}


class YLOMNIHUD_OT_sort_meshcheck_results(bpy.types.Operator):
    bl_idname = "yl_omnihud.sort_meshcheck_results"
    bl_label = "Sort Mesh Check Results"
    bl_description = "Sort the current mode results by the selected column"
    bl_options = {'INTERNAL'}

    sort_by: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return getattr(context, "mode", None) == 'OBJECT'

    def execute(self, context):
        settings = context.scene.yl_omnihud_meshcheck
        if settings.mode == 'PREVIEW':
            if settings.preview_sort_by == self.sort_by:
                settings.preview_sort_descending = not settings.preview_sort_descending
            else:
                settings.preview_sort_by = self.sort_by
                settings.preview_sort_descending = True
            sort_existing_preview_results(context, activate_first=True)
            sync_active_preview_selection(context)
            sync_preview_focus(context)
        else:
            if not _is_sortable_check_column(settings, self.sort_by):
                settings.check_sort_by = 'NAME'
                settings.check_sort_descending = False
                sort_existing_check_results(context, activate_first=True)
                sync_active_check_selection(context)
                return {'FINISHED'}
            if self.sort_by == 'NAME':
                if settings.check_sort_by == self.sort_by:
                    settings.check_sort_descending = not settings.check_sort_descending
                else:
                    settings.check_sort_by = self.sort_by
                    settings.check_sort_descending = True
            else:
                if settings.check_sort_by == self.sort_by:
                    settings.check_sort_descending = not settings.check_sort_descending
                else:
                    settings.check_sort_by = self.sort_by
                    settings.check_sort_descending = True
            sort_existing_check_results(context, activate_first=True)
            sync_active_check_selection(context)
        return {'FINISHED'}


class YLOMNIHUD_OT_refresh_meshcheck_results(bpy.types.Operator):
    bl_idname = "yl_omnihud.refresh_meshcheck_results"
    bl_label = "Refresh Analysis Results"
    bl_description = "Rebuild the current preview or check results"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        settings = getattr(getattr(context, "scene", None), "yl_omnihud_meshcheck", None)
        if settings is None:
            return {'CANCELLED'}

        checked_count, result_count = refresh_meshcheck_results(context)
        if checked_count <= 0:
            self.report({'WARNING'}, translate("No mesh objects found in the current scope"))
            return {'CANCELLED'}
        return {'FINISHED'}


class YLOMNIHUD_OT_toggle_all_check_visibility(bpy.types.Operator):
    bl_idname = "yl_omnihud.toggle_all_check_visibility"
    bl_label = "Toggle All Check Visibility"
    bl_description = "Enable or disable all check overlays"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        settings = getattr(context.scene, "yl_omnihud_meshcheck", None)
        if settings is None:
            return {'CANCELLED'}

        settings.show_all_checks = not _all_check_visibility_enabled(settings)
        return {'FINISHED'}
