import bpy
from bpy.props import EnumProperty

from .logic import refresh_heatmap


def _update_scope(self, context):
    del self
    if context is not None:
        refresh_heatmap(context)


class YLOMNIHUD_HeatmapSettings(bpy.types.PropertyGroup):
    scope: EnumProperty(
        name="Scope",
        items=[
            ('VISIBLE', "Visible", "Analyze visible mesh objects only"),
            ('SELECTED', "Selected", "Analyze selected mesh objects only"),
            ('ALL', "All", "Analyze all mesh objects in the current view layer"),
        ],
        default='ALL',
        update=_update_scope,
    )
