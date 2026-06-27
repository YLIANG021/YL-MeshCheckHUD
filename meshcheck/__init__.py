import bpy

from .handlers import register_handlers, unregister_handlers
from .operators import (
    YLOMNIHUD_OT_preview_meshcheck,
    YLOMNIHUD_OT_refresh_meshcheck_results,
    YLOMNIHUD_OT_sort_meshcheck_results,
    YLOMNIHUD_OT_toggle_all_check_visibility,
)
from .properties import (
    YLOMNIHUD_CheckResultItem,
    YLOMNIHUD_MeshCheckSettings,
    YLOMNIHUD_PreviewResultItem,
    unregister_deferred_check_threshold_update,
)


def register():
    bpy.utils.register_class(YLOMNIHUD_PreviewResultItem)
    bpy.utils.register_class(YLOMNIHUD_CheckResultItem)
    bpy.utils.register_class(YLOMNIHUD_MeshCheckSettings)
    bpy.utils.register_class(YLOMNIHUD_OT_preview_meshcheck)
    bpy.utils.register_class(YLOMNIHUD_OT_refresh_meshcheck_results)
    bpy.utils.register_class(YLOMNIHUD_OT_sort_meshcheck_results)
    bpy.utils.register_class(YLOMNIHUD_OT_toggle_all_check_visibility)
    bpy.types.Scene.yl_omnihud_meshcheck = bpy.props.PointerProperty(type=YLOMNIHUD_MeshCheckSettings)
    register_handlers()


def unregister():
    unregister_deferred_check_threshold_update()
    unregister_handlers()
    del bpy.types.Scene.yl_omnihud_meshcheck
    bpy.utils.unregister_class(YLOMNIHUD_OT_toggle_all_check_visibility)
    bpy.utils.unregister_class(YLOMNIHUD_OT_sort_meshcheck_results)
    bpy.utils.unregister_class(YLOMNIHUD_OT_refresh_meshcheck_results)
    bpy.utils.unregister_class(YLOMNIHUD_OT_preview_meshcheck)
    bpy.utils.unregister_class(YLOMNIHUD_MeshCheckSettings)
    bpy.utils.unregister_class(YLOMNIHUD_CheckResultItem)
    bpy.utils.unregister_class(YLOMNIHUD_PreviewResultItem)
