import math

import gpu
from gpu_extras.batch import batch_for_shader


BACKGROUND_SHADER = None
BACKGROUND_BATCH_CACHE = {}


def get_background_shader():
    global BACKGROUND_SHADER
    if BACKGROUND_SHADER is None:
        BACKGROUND_SHADER = gpu.shader.from_builtin("UNIFORM_COLOR")
    return BACKGROUND_SHADER


def append_arc_points(points, center_x, center_y, radius, start_angle, end_angle, segments):
    for index in range(1, segments + 1):
        angle = start_angle + ((end_angle - start_angle) * index / segments)
        points.append(
            (
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius,
            )
        )


def build_rounded_rect(left, bottom, right, top, radius, arc_segments=4):
    corner_radius = min(radius, max(0.0, (right - left) * 0.5), max(0.0, (top - bottom) * 0.5))

    points = [
        (left + corner_radius, bottom),
        (right - corner_radius, bottom),
    ]
    append_arc_points(
        points,
        right - corner_radius,
        bottom + corner_radius,
        corner_radius,
        -math.pi * 0.5,
        0.0,
        arc_segments,
    )

    points.append((right, top - corner_radius))
    append_arc_points(
        points,
        right - corner_radius,
        top - corner_radius,
        corner_radius,
        0.0,
        math.pi * 0.5,
        arc_segments,
    )

    points.append((left + corner_radius, top))
    append_arc_points(
        points,
        left + corner_radius,
        top - corner_radius,
        corner_radius,
        math.pi * 0.5,
        math.pi,
        arc_segments,
    )

    points.append((left, bottom + corner_radius))
    append_arc_points(
        points,
        left + corner_radius,
        bottom + corner_radius,
        corner_radius,
        math.pi,
        math.pi * 1.5,
        arc_segments,
    )

    return points


def get_background_batch(bg_rect):
    rect_key = tuple(bg_rect)
    batch = BACKGROUND_BATCH_CACHE.get(rect_key)
    if batch is None:
        shader = get_background_shader()
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": bg_rect})
        BACKGROUND_BATCH_CACHE[rect_key] = batch
        if len(BACKGROUND_BATCH_CACHE) > 32:
            BACKGROUND_BATCH_CACHE.pop(next(iter(BACKGROUND_BATCH_CACHE)))
    return batch


def draw_filled_rounded_rect(left, bottom, right, top, radius, color):
    bg_rect = build_rounded_rect(left, bottom, right, top, radius)
    shader = get_background_shader()
    batch = get_background_batch(bg_rect)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
