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
from .._registration import register_classes, unregister_classes


CLASSES = (
    YLOMNIHUD_PT_main,
    YLOMNIHUD_PT_meshcheck,
    YLOMNIHUD_UL_check_results,
    YLOMNIHUD_UL_preview_results,
)


def register():
    try:
        icons.register()
        register_classes(CLASSES)
    except Exception:
        unregister()
        raise


def unregister():
    unregister_classes(CLASSES)
    icons.unregister()
