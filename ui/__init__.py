import bpy

from . import icons
from .meshcheck_panel import (
    YLOMNIHUD_PT_meshcheck,
    YLOMNIHUD_UL_check_results,
    YLOMNIHUD_UL_preview_results,
)
from .panels import (
    YLOMNIHUD_PT_main,
)


def register():
    icons.register()
    bpy.utils.register_class(YLOMNIHUD_PT_main)
    bpy.utils.register_class(YLOMNIHUD_PT_meshcheck)
    bpy.utils.register_class(YLOMNIHUD_UL_check_results)
    bpy.utils.register_class(YLOMNIHUD_UL_preview_results)


def unregister():
    bpy.utils.unregister_class(YLOMNIHUD_UL_preview_results)
    bpy.utils.unregister_class(YLOMNIHUD_UL_check_results)
    bpy.utils.unregister_class(YLOMNIHUD_PT_meshcheck)
    bpy.utils.unregister_class(YLOMNIHUD_PT_main)
    icons.unregister()
