import bpy

from .core import CACHE, deferred_update, ensure_update_timer, tag_update_dirty
from .draw import draw_callback_px


DRAW_HANDLER = None


def register_handlers():
    """Register draw and update handlers."""
    global DRAW_HANDLER

    if DRAW_HANDLER is None:
        DRAW_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px,
            (),
            "WINDOW",
            "POST_PIXEL",
        )

    tag_update_dirty()
    ensure_update_timer()


def unregister_handlers():
    """Unregister draw and update handlers."""
    global DRAW_HANDLER

    if bpy.app.timers.is_registered(deferred_update):
        bpy.app.timers.unregister(deferred_update)

    if DRAW_HANDLER is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER, "WINDOW")
        DRAW_HANDLER = None

    CACHE["data"] = None
    CACHE["text_layout"] = {}
    CACHE["text_signature"] = None
    CACHE["needs_update"] = False
    CACHE["edit_trigger_signature"] = None
    CACHE["edit_geometry_signature"] = None
    CACHE["edit_geometry_signature_time"] = 0.0
