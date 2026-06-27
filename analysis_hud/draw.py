import blf
import bpy
import gpu

from ..overlay.core import get_prefs
from .core import get_analysis_hud_payload
from ..ui.draw_utils import draw_filled_rounded_rect


FONT_ID = 0
ITEM_GAP = 16
PAIR_GAP = 6
BACKGROUND_BASE_COLOR = (0.09, 0.09, 0.11)
LABEL_COLOR = (0.95, 0.78, 0.32, 0.95)
VALUE_COLOR = (1.0, 1.0, 1.0, 1.0)


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


def _measure_items(font_id, font_size, items):
    widths = []
    total_width = 0.0
    line_height = blf.dimensions(font_id, "X")[1]

    for index, item in enumerate(items):
        label_width = _text_width(font_id, item["label"], font_size)
        value_width = _text_width(font_id, item["value"], font_size)
        pair_width = label_width + PAIR_GAP + value_width
        widths.append((label_width, value_width, pair_width))
        total_width += pair_width
        if index < len(items) - 1:
            total_width += ITEM_GAP

    return widths, total_width, line_height


def _resolve_position(region, prefs, total_width, total_height, pad):
    margin_x = prefs.ui_x_offset
    margin_y = prefs.ui_y_offset
    position = prefs.ui_position

    y = float(margin_y + pad)
    if position == "LB":
        x = margin_x + pad
    else:
        x = region.width - total_width - margin_x - pad

    return max(pad, x), max(pad, y)


def draw_callback_px():
    context = bpy.context
    payload = get_analysis_hud_payload(context)
    if payload is None:
        return

    prefs = get_prefs()
    if prefs is None:
        return

    region = getattr(context, "region", None)
    if region is None:
        return

    font_size = int(getattr(prefs, "font_size", 14))
    blf.size(FONT_ID, font_size)
    items = payload["items"]
    widths, content_width, line_height = _measure_items(FONT_ID, font_size, items)

    if not widths or content_width <= 0 or line_height <= 0:
        return

    total_width = content_width
    total_height = line_height
    pad = 5.0 if getattr(prefs, "enable_background", True) else 0.0
    x, y = _resolve_position(region, prefs, total_width, total_height, pad)
    card_left = x - pad
    card_bottom = y - pad
    card_right = x + total_width + pad
    card_top = y + total_height + pad

    gpu.state.blend_set("ALPHA")
    if getattr(prefs, "enable_background", True):
        draw_filled_rounded_rect(
            card_left,
            card_bottom,
            card_right,
            card_top,
            radius=8 * 0.666,
            color=(*BACKGROUND_BASE_COLOR, prefs.background_opacity / 100.0),
        )

    cursor_x = x
    baseline_y = y
    for index, item in enumerate(items):
        label_width, _value_width, pair_width = widths[index]

        label_color = VALUE_COLOR if item.get("is_neutral") else LABEL_COLOR
        blf.color(FONT_ID, *label_color)
        blf.position(FONT_ID, cursor_x, baseline_y, 0)
        blf.draw(FONT_ID, item["label"])

        blf.color(FONT_ID, *VALUE_COLOR)
        blf.position(FONT_ID, cursor_x + label_width + PAIR_GAP, baseline_y, 0)
        blf.draw(FONT_ID, item["value"])

        cursor_x += pair_width
        if index < len(items) - 1:
            cursor_x += ITEM_GAP

    gpu.state.blend_set("NONE")
