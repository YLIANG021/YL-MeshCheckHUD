import bpy

from ..heatmap.logic import (
    get_focused_object,
    get_focused_object_ratio,
    get_stored_complexity_value,
    is_heatmap_active,
    is_preview_owner_context,
)
from ..i18n import pgettext
from ..meshcheck.core import get_visible_check_definitions, is_meshcheck_owner_context
from ..overlay.core import get_prefs

HUD_LABEL_OVERRIDES = {
    "NON_MANIFOLD": "Non-manifold",
}


def _check_label(definition, settings):
    if definition["id"] == "POLES":
        return f'{pgettext("Poles")} > {settings.pole_threshold}'
    return pgettext(HUD_LABEL_OVERRIDES.get(definition["id"], definition["label"]))


def _get_meshcheck_settings(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return None
    return getattr(scene, "yl_omnihud_meshcheck", None)


def _get_active_check_result(settings):
    if settings is None or not settings.check_results:
        return None

    index = settings.active_check_index
    if index < 0 or index >= len(settings.check_results):
        return None
    return settings.check_results[index]


def _preview_payload(context, settings):
    del settings
    if not is_heatmap_active(context) or not is_preview_owner_context(context):
        return None

    focused_object = get_focused_object(context)
    if focused_object is None:
        return None

    tris = get_stored_complexity_value(context, focused_object)
    ratio = get_focused_object_ratio(context) * 100.0
    return {
        "mode": "PREVIEW",
        "items": (
            {"label": "Tris", "value": f"{tris:,}"},
            {"label": "%", "value": f"{ratio:.1f}%"},
        ),
    }


def _check_payload(context, settings):
    if settings is None or not settings.show_overlay or not is_meshcheck_owner_context(context):
        return None

    item = _get_active_check_result(settings)
    if item is None:
        return None

    entries = []
    for definition in get_visible_check_definitions(context):
        label = _check_label(definition, settings)
        attr_name = definition["count_attr"]
        value = int(getattr(item, attr_name, 0))
        if value <= 0:
            continue
        entries.append({"label": label, "value": str(value)})

    if not entries:
        entries.append({"label": pgettext("No Findings"), "value": "", "is_neutral": True})

    return {
        "mode": "CHECK",
        "items": tuple(entries),
    }


def get_analysis_hud_payload(context):
    if context is None:
        return None

    prefs = get_prefs()
    if prefs is None or not getattr(prefs, "enable_display", False):
        return None

    settings = _get_meshcheck_settings(context)
    if settings is None:
        return None

    if not is_heatmap_active(context) and not getattr(settings, "show_overlay", False):
        return None

    if settings.mode == "PREVIEW":
        return _preview_payload(context, settings)
    return _check_payload(context, settings)


def tag_view3d_redraw():
    context = bpy.context
    if context is None:
        return

    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return

    for window in window_manager.windows:
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
