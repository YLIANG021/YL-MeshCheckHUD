import bpy

from .draw import draw_callback_px, draw_callback_view
from .logic import (
    clear_heatmap,
    has_preview_refresh_signature_changed,
    is_heatmap_active,
    refresh_heatmap,
    sync_heatmap_display_for_mode,
)


DRAW_HANDLER_VIEW = None
DRAW_HANDLER_PIXEL = None
PREVIEW_REFRESH_INTERVAL = 0.08


def deferred_preview_refresh():
    context = bpy.context
    if not context:
        return None

    if not is_heatmap_active(context):
        return None

    if sync_heatmap_display_for_mode(context):
        return None

    if has_preview_refresh_signature_changed(context):
        refresh_heatmap(context)

    return None


@bpy.app.handlers.persistent
def on_depsgraph_update(scene=None, depsgraph=None):
    del scene
    del depsgraph

    context = bpy.context
    if not context or not is_heatmap_active(context):
        return

    if bpy.app.timers.is_registered(deferred_preview_refresh):
        return

    bpy.app.timers.register(deferred_preview_refresh, first_interval=PREVIEW_REFRESH_INTERVAL)


@bpy.app.handlers.persistent
def on_file_load(dummy):
    del dummy

    context = bpy.context
    if not context or getattr(context, "scene", None) is None:
        return

    try:
        clear_heatmap(context)
    except Exception:
        pass


def register_handlers():
    global DRAW_HANDLER_VIEW, DRAW_HANDLER_PIXEL

    if DRAW_HANDLER_VIEW is None:
        DRAW_HANDLER_VIEW = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_view,
            (),
            "WINDOW",
            "POST_VIEW",
        )

    if DRAW_HANDLER_PIXEL is None:
        DRAW_HANDLER_PIXEL = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px,
            (),
            "WINDOW",
            "POST_PIXEL",
        )

    if on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(on_depsgraph_update)

    if on_file_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load)


def unregister_handlers():
    global DRAW_HANDLER_VIEW, DRAW_HANDLER_PIXEL

    if bpy.app.timers.is_registered(deferred_preview_refresh):
        bpy.app.timers.unregister(deferred_preview_refresh)

    if DRAW_HANDLER_VIEW is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER_VIEW, "WINDOW")
        DRAW_HANDLER_VIEW = None

    if DRAW_HANDLER_PIXEL is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER_PIXEL, "WINDOW")
        DRAW_HANDLER_PIXEL = None

    if on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(on_depsgraph_update)

    if on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load)
