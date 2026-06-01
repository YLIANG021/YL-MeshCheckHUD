import bpy

from . import handlers
from .prefs import RTD_Preferences
from .._registration import register_classes, unregister_classes


CLASSES = (RTD_Preferences,)


def register():
    try:
        register_classes(CLASSES)
        handlers.register_handlers()
    except Exception:
        unregister()
        raise


def unregister():
    handlers.unregister_handlers()
    unregister_classes(CLASSES)
