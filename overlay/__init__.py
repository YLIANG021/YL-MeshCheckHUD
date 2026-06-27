import bpy

from . import handlers
from .prefs import RTD_Preferences


def register():
    bpy.utils.register_class(RTD_Preferences)
    handlers.register_handlers()


def unregister():
    handlers.unregister_handlers()
    bpy.utils.unregister_class(RTD_Preferences)
