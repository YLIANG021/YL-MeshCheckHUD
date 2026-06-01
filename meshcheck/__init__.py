import bpy

from .handlers import register_handlers, unregister_handlers
from .operators import (
    YLOMNIHUD_OT_preview_meshcheck,
    YLOMNIHUD_OT_refresh_meshcheck_results,
    YLOMNIHUD_OT_sort_meshcheck_results,
    YLOMNIHUD_OT_toggle_all_check_visibility,
    unregister_deferred_check_refresh,
)
from .properties import (
    YLOMNIHUD_CheckResultItem,
    YLOMNIHUD_MeshCheckSettings,
    YLOMNIHUD_PreviewResultItem,
)
from .._registration import register_classes, unregister_classes


CLASSES = (
    YLOMNIHUD_PreviewResultItem,
    YLOMNIHUD_CheckResultItem,
    YLOMNIHUD_MeshCheckSettings,
    YLOMNIHUD_OT_preview_meshcheck,
    YLOMNIHUD_OT_refresh_meshcheck_results,
    YLOMNIHUD_OT_sort_meshcheck_results,
    YLOMNIHUD_OT_toggle_all_check_visibility,
)


def register():
    try:
        register_classes(CLASSES)
        bpy.types.Scene.yl_omnihud_meshcheck = bpy.props.PointerProperty(type=YLOMNIHUD_MeshCheckSettings)
        register_handlers()
    except Exception:
        unregister()
        raise


def unregister():
    unregister_deferred_check_refresh()
    unregister_handlers()
    if hasattr(bpy.types.Scene, "yl_omnihud_meshcheck"):
        del bpy.types.Scene.yl_omnihud_meshcheck
    unregister_classes(CLASSES)
