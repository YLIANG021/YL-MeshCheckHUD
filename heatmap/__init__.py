import bpy

from .handlers import register_handlers, unregister_handlers
from .logic import clear_heatmap
from .properties import YLOMNIHUD_HeatmapSettings
from .._registration import register_classes, unregister_classes


CLASSES = (
    YLOMNIHUD_HeatmapSettings,
)


def register():
    try:
        register_classes(CLASSES)
        bpy.types.Scene.yl_omnihud_heatmap = bpy.props.PointerProperty(type=YLOMNIHUD_HeatmapSettings)
        register_handlers()
    except Exception:
        unregister()
        raise


def unregister():
    context = bpy.context
    if context is not None and getattr(context, "scene", None) is not None:
        try:
            clear_heatmap(context)
        except Exception:
            pass
    unregister_handlers()

    if hasattr(bpy.types.Scene, "yl_omnihud_heatmap"):
        del bpy.types.Scene.yl_omnihud_heatmap
    unregister_classes(CLASSES)
