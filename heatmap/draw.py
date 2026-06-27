import blf
import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from ..overlay.core import get_prefs
from ..ui.draw_utils import draw_filled_rounded_rect
from .logic import (
    get_focused_object,
    get_focused_object_rank,
    get_focused_object_ratio,
    is_preview_owner_context,
    get_stored_complexity_value,
    is_heatmap_active,
)


LINE_SHADER = None

HIGHLIGHT_COLOR = (1.0, 0.62, 0.18, 0.95)
FRAME_COLOR = (1.0, 0.72, 0.28, 0.95)
TAG_BG_COLOR = (0.08, 0.08, 0.08)
TAG_TEXT_COLOR = (1.0, 0.92, 0.72, 1.0)
LINE_WIDTH = 2.5
FONT_ID = 0
CORNER_LENGTH_MAX = 24.0
CORNER_LENGTH_MIN = 4.0
FRAME_PADDING_MAX = 14.0
FRAME_PADDING_MIN = 2.0
MIN_FRAME_SIZE = 9.0
TAG_PADDING_X = 8.0
TAG_PADDING_Y = 5.0
TAG_TEXT_BASELINE_OFFSET_Y = 2.0


def _get_line_shader():
    global LINE_SHADER

    if LINE_SHADER is None:
        LINE_SHADER = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    return LINE_SHADER


def _get_bbox_world_corners(obj):
    matrix = obj.matrix_world
    return [matrix @ Vector(corner) for corner in obj.bound_box]


def _draw_lines_2d(segments, color, line_width=LINE_WIDTH):
    shader = _get_line_shader()
    viewport = gpu.state.viewport_get()
    batch = batch_for_shader(shader, "LINES", {"pos": segments})
    shader.bind()
    shader.uniform_float("viewportSize", (viewport[2], viewport[3]))
    shader.uniform_float("lineWidth", line_width)
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_rect_2d(left, bottom, right, top, color):
    segments = [
        (left, bottom), (right, bottom),
        (right, bottom), (right, top),
        (right, top), (left, top),
        (left, top), (left, bottom),
    ]
    _draw_lines_2d(segments, color, line_width=1.2)


def _get_screen_bounds(region, region_data, corners):
    points = []
    for corner in corners:
        point = location_3d_to_region_2d(region, region_data, corner)
        if point is not None:
            points.append(point)

    if not points:
        return None

    min_x = min(point.x for point in points)
    max_x = max(point.x for point in points)
    min_y = min(point.y for point in points)
    max_y = max(point.y for point in points)

    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    width = max(max_x - min_x, MIN_FRAME_SIZE)
    height = max(max_y - min_y, MIN_FRAME_SIZE)
    padding = max(FRAME_PADDING_MIN, min(FRAME_PADDING_MAX, min(width, height) * 0.12))

    half_width = width * 0.5 + padding
    half_height = height * 0.5 + padding
    return (
        center_x - half_width,
        center_y - half_height,
        center_x + half_width,
        center_y + half_height,
    )


def _build_corner_segments(left, bottom, right, top):
    frame_width = right - left
    frame_height = top - bottom
    corner_length = max(
        CORNER_LENGTH_MIN,
        min(CORNER_LENGTH_MAX, min(frame_width, frame_height) * 0.22),
    )
    horizontal = min(corner_length, frame_width * 0.35)
    vertical = min(corner_length, frame_height * 0.35)

    return [
        (left, bottom + vertical), (left, bottom),
        (left, bottom), (left + horizontal, bottom),

        (right - horizontal, bottom), (right, bottom),
        (right, bottom), (right, bottom + vertical),

        (right, top - vertical), (right, top),
        (right, top), (right - horizontal, top),

        (left + horizontal, top), (left, top),
        (left, top), (left, top - vertical),
    ]


def _draw_tag(label, left, top):
    prefs = get_prefs()
    background_alpha = (getattr(prefs, "background_opacity", 50) / 100.0) if prefs is not None else 0.5
    text_width, text_height = blf.dimensions(FONT_ID, label)
    tag_left = left
    tag_bottom = top + 10.0
    tag_right = tag_left + text_width + TAG_PADDING_X * 2.0
    tag_top = tag_bottom + text_height + TAG_PADDING_Y * 2.0

    gpu.state.blend_set("ALPHA")
    draw_filled_rounded_rect(tag_left, tag_bottom, tag_right, tag_top, 5.0, (*TAG_BG_COLOR, background_alpha))
    gpu.state.blend_set("NONE")

    blf.color(FONT_ID, *TAG_TEXT_COLOR)
    blf.position(FONT_ID, tag_left + TAG_PADDING_X, tag_bottom + TAG_PADDING_Y + TAG_TEXT_BASELINE_OFFSET_Y, 0)
    blf.draw(FONT_ID, label)


def draw_callback_px():
    context = bpy.context
    if context is None or not is_heatmap_active(context) or not is_preview_owner_context(context):
        return
    if getattr(context, "mode", "") != 'OBJECT':
        return

    region = getattr(context, "region", None)
    region_data = getattr(context, "region_data", None)
    focused_object = get_focused_object(context)
    if region is None or region_data is None or focused_object is None:
        return

    corners = _get_bbox_world_corners(focused_object)
    bounds = _get_screen_bounds(region, region_data, corners)
    if bounds is None:
        return

    left, bottom, right, top = bounds
    corner_segments = _build_corner_segments(left, bottom, right, top)
    rank, total = get_focused_object_rank(context)
    ratio = get_focused_object_ratio(context) * 100.0
    tris_count = get_stored_complexity_value(context, focused_object)
    label = f"TOP {rank}/{total}  {tris_count:,} tris  {ratio:.1f}%"

    blf.size(FONT_ID, 13)
    gpu.state.blend_set("ALPHA")
    _draw_lines_2d(corner_segments, FRAME_COLOR)
    gpu.state.blend_set("NONE")
    _draw_tag(label, left, top)
