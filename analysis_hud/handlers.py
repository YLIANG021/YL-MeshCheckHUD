import bpy

from .core import tag_view3d_redraw
from .draw import draw_callback_px


DRAW_HANDLER = None


def register_handlers():
    global DRAW_HANDLER

    if DRAW_HANDLER is None:
        DRAW_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px,
            (),
            "WINDOW",
            "POST_PIXEL",
        )

    tag_view3d_redraw()


def unregister_handlers():
    global DRAW_HANDLER

    if DRAW_HANDLER is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER, "WINDOW")
        DRAW_HANDLER = None

    tag_view3d_redraw()
