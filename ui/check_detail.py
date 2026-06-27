import bpy

from ..i18n import pgettext
from ..meshcheck.definitions import CHECK_DEFINITIONS
from .icons import get_check_icon_fallback, get_check_icon_value

translate = bpy.app.translations.pgettext_iface


def should_draw_check_detail(context, settings):
    return (
        getattr(context, "mode", "") == 'EDIT_MESH'
        and settings is not None
        and getattr(settings, "mode", "") == 'CHECK'
        and bool(getattr(settings, "show_overlay", False))
    )


def get_check_detail_title(context):
    object_name = _active_mesh_name(context)
    title = translate("Check Results")
    if not object_name:
        return title
    return f"{object_name} \N{MIDDLE DOT} {title}"


def _active_mesh_name(context):
    view_layer = getattr(context, "view_layer", None)
    active_object = getattr(view_layer.objects, "active", None) if view_layer is not None else None
    if active_object is None or getattr(active_object, "type", None) != 'MESH':
        return ""
    return active_object.name


def _find_check_result(settings, object_name):
    if not object_name:
        return None
    for item in getattr(settings, "check_results", ()):
        if getattr(item, "object_name", "") == object_name:
            return item
    return None


def _check_label(definition, settings):
    if definition["id"] == "POLES":
        return f'{translate("Poles")} > {settings.pole_threshold}'
    if definition["id"] == "MISSING_SHARP":
        return f'{pgettext("Sharp")} > {settings.missing_sharp_angle:g}\N{DEGREE SIGN}'
    return translate(definition["label"])


def _check_count(item, definition):
    try:
        return max(0, int(getattr(item, definition["count_attr"], 0)))
    except (TypeError, ValueError):
        return 0


def _draw_check_icon(row, settings, definition, enabled):
    icon_value = get_check_icon_value(definition["id"], enabled)
    if icon_value:
        row.prop(
            settings,
            definition["show_prop"],
            text="",
            icon_value=icon_value,
            toggle=True,
            emboss=False,
        )
    else:
        row.prop(
            settings,
            definition["show_prop"],
            text="",
            icon=get_check_icon_fallback(definition["id"], enabled),
            toggle=True,
            emboss=False,
        )


def draw_check_detail(container, context, settings):
    object_name = _active_mesh_name(context)
    item = _find_check_result(settings, object_name)

    if item is None:
        container.label(text=translate("Enable HUD to generate results."), icon='INFO')
        return

    body = container.column(align=True)
    visible_definitions = [
        definition
        for definition in CHECK_DEFINITIONS
        if getattr(settings, definition.get("display_prop", ""), True)
    ]

    for definition in visible_definitions:
        enabled = bool(getattr(settings, definition["show_prop"], False))
        count = _check_count(item, definition)

        row = body.box().row(align=True)
        _draw_check_icon(row, settings, definition, enabled)

        detail_row = row.row(align=True)
        split = detail_row.split(factor=0.72, align=True)
        split.enabled = enabled
        label_cell = split.row(align=True)
        label_cell.label(text=_check_label(definition, settings))

        value_cell = split.row(align=True)
        value_cell.alignment = 'RIGHT'
        value_cell.label(text=f"{count:,}" if enabled else "—")
