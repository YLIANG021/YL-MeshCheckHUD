import bpy

from .handlers import register_handlers, unregister_handlers
from .logic import clear_heatmap
from .properties import YLOMNIHUD_HeatmapSettings


def register():
    bpy.utils.register_class(YLOMNIHUD_HeatmapSettings)
    bpy.types.Scene.yl_omnihud_heatmap = bpy.props.PointerProperty(type=YLOMNIHUD_HeatmapSettings)
    register_handlers()


def unregister():
    context = bpy.context
    if context is not None and getattr(context, "scene", None) is not None:
        clear_heatmap(context)
    unregister_handlers()

    del bpy.types.Scene.yl_omnihud_heatmap
    bpy.utils.unregister_class(YLOMNIHUD_HeatmapSettings)
