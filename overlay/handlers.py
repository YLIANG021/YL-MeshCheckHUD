import bpy

from .core import CACHE, deferred_update, tag_update_dirty
from .draw import draw_callback_px


DRAW_HANDLER = None


@bpy.app.handlers.persistent
def on_file_load(dummy):
    """Refresh overlay data after loading a new blend file."""
    del dummy
    tag_update_dirty()


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

    if tag_update_dirty not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(tag_update_dirty)

    if on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load)

    tag_update_dirty()


def unregister_handlers():
    """Unregister draw and update handlers."""
    global DRAW_HANDLER

    if bpy.app.timers.is_registered(deferred_update):
        bpy.app.timers.unregister(deferred_update)

    if DRAW_HANDLER is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER, "WINDOW")
        DRAW_HANDLER = None

    if tag_update_dirty in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(tag_update_dirty)

    if on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load)

    CACHE["data"] = None
    CACHE["text_layout"] = {}
    CACHE["text_signature"] = None
    CACHE["needs_update"] = False
