import bpy

from .core import tag_view3d_redraw
from .draw import draw_callback_px


DRAW_HANDLER = None


@bpy.app.handlers.persistent
def on_file_load(dummy):
    del dummy
    tag_view3d_redraw()


def register_handlers():
    global DRAW_HANDLER

    if DRAW_HANDLER is None:
        DRAW_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px,
            (),
            "WINDOW",
            "POST_PIXEL",
        )

    if on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load)

    tag_view3d_redraw()


def unregister_handlers():
    global DRAW_HANDLER

    if DRAW_HANDLER is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER, "WINDOW")
        DRAW_HANDLER = None

    if on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load)

    tag_view3d_redraw()
