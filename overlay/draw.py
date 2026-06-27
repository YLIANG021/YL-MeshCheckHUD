import blf
import bpy
import gpu

from ..heatmap.logic import is_heatmap_active
from .core import CACHE, get_prefs
from ..ui.draw_utils import draw_filled_rounded_rect

translate = bpy.app.translations.pgettext_iface
MAIN_ITEM_GAP = 18.0


def _text_width(font_id, text, font_size):
    if not text:
        return 0.0

    full_width = blf.dimensions(font_id, text)[0]
    char_widths = [blf.dimensions(font_id, char)[0] for char in text]
    summed_width = sum(char_widths)
    if full_width > 0.0 or summed_width > 0.0:
        return max(full_width, summed_width)

    fallback_width = 0.0
    for char in text:
        fallback_width += font_size * (0.35 if char.isspace() else 0.7)
    return fallback_width


def _get_unit_settings(data):
    if not data["show_units"]:
        return 1.0, ""

    if data.get("auto_unit"):
        dims = data.get("dims")
        if dims is not None and max(dims.x, dims.y, dims.z) < 1.0:
            return 100.0, " cm"
        return 1.0, " m"

    if data["unit_sys"] == "cm":
        return 100.0, " cm"
    if data["unit_sys"] == "mm":
        return 1000.0, " mm"
    return 1.0, " m"


def _build_dimension_labels(dims, unit_scale, unit_suffix):
    if dims is None:
        return "", "", ""

    scaled = dims * unit_scale
    return (
        f"{scaled.x:.2f}{unit_suffix}",
        f"{scaled.y:.2f}{unit_suffix}",
        f"{scaled.z:.2f}{unit_suffix}",
    )


def _measure_layout(font_id, font_size, tris_text, x_text, y_text, z_text, has_dims):
    layout = {
        "tris_w": _text_width(font_id, tris_text, font_size),
        "sep_w": MAIN_ITEM_GAP,
        "x_w": _text_width(font_id, x_text, font_size),
        "y_w": _text_width(font_id, y_text, font_size),
        "z_w": _text_width(font_id, z_text, font_size),
        "h": blf.dimensions(font_id, "X")[1],
    }

    main_width = layout["tris_w"]
    if has_dims:
        main_width += layout["sep_w"] * 3 + layout["x_w"] + layout["y_w"] + layout["z_w"]
    layout["main_w"] = main_width
    return layout


def _measure_secondary_layout(font_id, font_size, warning_text, selection_count_text):
    return {
        "warning_w": _text_width(font_id, warning_text, font_size),
        "selection_w": _text_width(font_id, selection_count_text, font_size),
        "line_h": blf.dimensions(font_id, "X")[1] if (warning_text or selection_count_text) else 0,
    }


def _build_warning_text(data):
    warnings = []
    if data.get("show_unapplied_scale") and data["unapplied_scale"]:
        warnings.append(translate("Unapplied Scale"))
    if data["high_poly"]:
        warning_text = translate("High Face Count")
        if data.get("show_high_poly_threshold"):
            warning_text = f"{warning_text} >{data['high_poly_threshold_label']}"
        warnings.append(warning_text)
    return "    ".join(warnings)


def _build_selection_count_text(data):
    selected_count = data.get("selected_count", 0)
    if selected_count <= 1:
        return ""
    return translate("{count} Objects").format(count=selected_count)


def draw_callback_px():
    """Draw the 3D View overlay."""
    context = bpy.context
    if context is not None:
        scene = getattr(context, "scene", None)
        meshcheck_settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
        if is_heatmap_active(context) or bool(getattr(meshcheck_settings, "show_overlay", False)):
            return

    data = CACHE.get("data")
    if not data:
        return

    prefs = get_prefs()
    if not prefs:
        return

    font_id = 0
    blf.size(font_id, prefs.font_size)

    unit_scale, unit_suffix = _get_unit_settings(data)
    dims = data["dims"]
    x_text, y_text, z_text = _build_dimension_labels(dims, unit_scale, unit_suffix)

    count_label = data.get("count_label", "Tris")
    tris_text = f"{count_label}: {data['tris']}"
    warning_text = _build_warning_text(data)
    selection_count_text = _build_selection_count_text(data)

    layout = _measure_layout(font_id, prefs.font_size, tris_text, x_text, y_text, z_text, dims is not None)
    warning_font_size = max(10, int(round(prefs.font_size * 0.82)))
    blf.size(font_id, warning_font_size)
    secondary_layout = _measure_secondary_layout(font_id, warning_font_size, warning_text, selection_count_text)
    warning_width = secondary_layout["warning_w"]
    selection_count_width = secondary_layout["selection_w"]
    secondary_line_height = secondary_layout["line_h"]
    blf.size(font_id, prefs.font_size)

    region = context.region if context is not None else None
    if not region:
        return

    margin_x = prefs.ui_x_offset
    margin_y = prefs.ui_y_offset
    position = prefs.ui_position

    pad = 5 if prefs.enable_background else 0
    x = 0
    y = margin_y + pad
    main_width = layout["main_w"]
    has_secondary_line = bool(warning_text or selection_count_text)
    line_gap = 6 if has_secondary_line else 0
    secondary_gap = 20 if warning_text and selection_count_text else 0
    secondary_width = warning_width + secondary_gap + selection_count_width
    total_width = max(main_width, secondary_width)
    total_height = layout["h"] + (line_gap + secondary_line_height if has_secondary_line else 0)

    if position == "LB":
        x = margin_x + pad
    else:
        x = region.width - total_width - margin_x - pad

    x = max(pad, x)
    y = max(pad, y)

    gpu.state.blend_set("ALPHA")
    if prefs.enable_background and total_width > 0:
        card_left = x - pad
        card_right = x + total_width + pad
        card_bottom = y - pad
        card_top = y + total_height + pad
        draw_filled_rounded_rect(
            card_left,
            card_bottom,
            card_right,
            card_top,
            radius=8 * 0.666,
            color=(0.09, 0.09, 0.11, prefs.background_opacity / 100.0),
        )

    current_x = x
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
    blf.position(font_id, current_x, y, 0)
    blf.draw(font_id, tris_text)
    current_x += layout["tris_w"]

    if dims is not None:
        current_x += layout["sep_w"]
        if prefs.use_axis_colors:
            blf.color(font_id, 1.0, 0.4, 0.4, 1.0)
            blf.position(font_id, current_x, y, 0)
            blf.draw(font_id, x_text)
            current_x += layout["x_w"] + layout["sep_w"]

            blf.color(font_id, 0.6, 1.0, 0.4, 1.0)
            blf.position(font_id, current_x, y, 0)
            blf.draw(font_id, y_text)
            current_x += layout["y_w"] + layout["sep_w"]

            blf.color(font_id, 0.4, 0.6, 1.0, 1.0)
            blf.position(font_id, current_x, y, 0)
            blf.draw(font_id, z_text)
        else:
            blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
            blf.position(font_id, current_x, y, 0)
            blf.draw(font_id, x_text)
            current_x += layout["x_w"] + layout["sep_w"]
            blf.position(font_id, current_x, y, 0)
            blf.draw(font_id, y_text)
            current_x += layout["y_w"] + layout["sep_w"]
            blf.position(font_id, current_x, y, 0)
            blf.draw(font_id, z_text)

    if warning_text or selection_count_text:
        blf.size(font_id, warning_font_size)
        second_line_y = y + layout["h"] + line_gap

        if warning_text:
            blf.color(font_id, 0.95, 0.78, 0.32, 0.9)
            blf.position(font_id, x, second_line_y, 0)
            blf.draw(font_id, warning_text)

        if selection_count_text:
            blf.color(font_id, 1.0, 1.0, 1.0, 0.92)
            blf.position(font_id, x + total_width - selection_count_width, second_line_y, 0)
            blf.draw(font_id, selection_count_text)

        blf.size(font_id, prefs.font_size)

    gpu.state.blend_set("NONE")
