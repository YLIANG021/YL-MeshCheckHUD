import bpy

from .draw import draw_callback_px
from .logic import (
    clear_heatmap,
    has_preview_refresh_signature_changed,
    is_heatmap_active,
    refresh_heatmap,
    scene_needs_cleanup,
    sync_heatmap_display_for_mode,
)


DRAW_HANDLER_PIXEL = None
HEATMAP_UPDATE_INTERVAL = 0.07


def _cleanup_handlers():
    return getattr(bpy.app.handlers, "exit_pre", None)


def refresh_active_heatmap():
    context = bpy.context
    if not context:
        return

    if not is_heatmap_active(context):
        return

    if sync_heatmap_display_for_mode(context):
        return

    if has_preview_refresh_signature_changed(context):
        refresh_heatmap(context)


def _ensure_heatmap_update_timer():
    if not bpy.app.timers.is_registered(process_heatmap_update):
        bpy.app.timers.register(
            process_heatmap_update,
            first_interval=HEATMAP_UPDATE_INTERVAL,
            persistent=True,
        )


def unregister_heatmap_update_timer():
    if bpy.app.timers.is_registered(process_heatmap_update):
        bpy.app.timers.unregister(process_heatmap_update)


def sync_heatmap_update_timer_state(context=None):
    if context is None:
        context = bpy.context

    if context is not None and is_heatmap_active(context):
        _ensure_heatmap_update_timer()
    else:
        unregister_heatmap_update_timer()


def process_heatmap_update():
    context = bpy.context
    if context is None:
        return None

    scene = getattr(context, "scene", None)
    if not is_heatmap_active(context):
        if scene_needs_cleanup(scene):
            clear_heatmap(context)
        return None

    refresh_active_heatmap()
    if is_heatmap_active(context):
        return HEATMAP_UPDATE_INTERVAL
    return None


@bpy.app.handlers.persistent
def on_exit_pre(dummy=None):
    del dummy

    context = bpy.context
    scene = getattr(context, "scene", None) if context is not None else None
    if scene is None:
        return

    if scene_needs_cleanup(scene):
        clear_heatmap(context)


def register_handlers():
    global DRAW_HANDLER_PIXEL

    if DRAW_HANDLER_PIXEL is None:
        DRAW_HANDLER_PIXEL = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px,
            (),
            "WINDOW",
            "POST_PIXEL",
        )

    cleanup_handlers = _cleanup_handlers()
    if cleanup_handlers is not None and on_exit_pre not in cleanup_handlers:
        cleanup_handlers.append(on_exit_pre)

    sync_heatmap_update_timer_state()


def unregister_handlers():
    global DRAW_HANDLER_PIXEL

    if DRAW_HANDLER_PIXEL is not None:
        bpy.types.SpaceView3D.draw_handler_remove(DRAW_HANDLER_PIXEL, "WINDOW")
        DRAW_HANDLER_PIXEL = None

    unregister_heatmap_update_timer()

    cleanup_handlers = _cleanup_handlers()
    if cleanup_handlers is not None and on_exit_pre in cleanup_handlers:
        cleanup_handlers.remove(on_exit_pre)
