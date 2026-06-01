import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from ..overlay.core import get_prefs
from .core.config import get_visible_check_definitions
from .core.results import (
    get_active_check_object_name,
    get_active_check_overlay_data,
    get_edit_mode_active_check_overlay_data,
)
from .core.runtime import is_meshcheck_owner_context

LINE_SHADER = None
POINT_SHADER = None
FACE_SHADER = None
DRAW_BATCH_CACHE = {}

LINE_WIDTH = 2.5
POINT_SIZE_MAX = 8.0
POINT_SIZE_MIN = 4.0
POINT_SIZE_FACTOR = 0.08
MAX_SEGMENT_PRIMITIVES = 12000
MAX_POINT_PRIMITIVES = 8000
MAX_FACE_PRIMITIVES = 1500
MAX_BATCH_CACHE_ITEMS = 16

def _use_xray_depth(context):
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is not None and getattr(settings, "mode", "") == 'CHECK' and getattr(settings, "check_use_xray", False):
        return True
    space = getattr(context, "space_data", None)
    shading = getattr(space, "shading", None) if space is not None else None
    return bool(getattr(shading, "show_xray", False)) if shading is not None else False


def _begin_overlay_depth_state(context):
    gpu.state.blend_set("ALPHA")
    if _use_xray_depth(context):
        gpu.state.depth_test_set("NONE")
    else:
        gpu.state.depth_test_set("LESS_EQUAL")


def _end_overlay_depth_state():
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")


def _get_line_shader():
    global LINE_SHADER
    if LINE_SHADER is None:
        LINE_SHADER = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    return LINE_SHADER


def _get_point_shader():
    global POINT_SHADER
    if POINT_SHADER is None:
        shader_info = gpu.types.GPUShaderCreateInfo()
        shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
        shader_info.push_constant('VEC4', "color")
        shader_info.push_constant('FLOAT', "size")
        shader_info.vertex_in(0, 'VEC3', "pos")
        shader_info.fragment_out(0, 'VEC4', "fragColor")
        shader_info.vertex_source(
            "void main()"
            "{"
            "  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);"
            "  gl_PointSize = size;"
            "}"
        )
        shader_info.fragment_source(
            "void main()"
            "{"
            "  vec2 centered = (gl_PointCoord * 2.0) - vec2(1.0);"
            "  float radius_sq = dot(centered, centered);"
            "  if (radius_sq > 1.0) discard;"
            "  float edge = smoothstep(1.0, 0.7, radius_sq);"
            "  fragColor = vec4(color.rgb, color.a * edge);"
            "}"
        )
        POINT_SHADER = gpu.shader.create_from_info(shader_info)
        del shader_info
    return POINT_SHADER


def _get_face_shader():
    global FACE_SHADER
    if FACE_SHADER is None:
        FACE_SHADER = gpu.shader.from_builtin("UNIFORM_COLOR")
    return FACE_SHADER


def _batch_cache_key(kind, object_name, color, offset, payload_size, payload_token, point_size=None):
    base = (
        kind,
        object_name,
        tuple(round(component, 6) for component in color),
        round(offset, 6),
        payload_size,
        payload_token,
    )
    if point_size is not None:
        return base + (round(point_size, 4),)
    return base


def _limit_payload(payload, limit):
    if not payload or limit <= 0 or len(payload) <= limit:
        return payload
    return payload[:limit]


def _store_batch_cache_entry(cache_key, batch):
    if len(DRAW_BATCH_CACHE) >= MAX_BATCH_CACHE_ITEMS:
        DRAW_BATCH_CACHE.clear()
    DRAW_BATCH_CACHE[cache_key] = batch


def _draw_segments(segments, color, offset=0.0, object_name="", payload_token=0):
    if not segments:
        return

    segments = _limit_payload(segments, MAX_SEGMENT_PRIMITIVES)
    shader = _get_line_shader()
    viewport = gpu.state.viewport_get()
    cache_key = _batch_cache_key("segments", object_name, color, offset, len(segments), payload_token)
    batch = DRAW_BATCH_CACHE.get(cache_key)
    if batch is None:
        coords = []
        for segment in segments:
            start = segment["start"] + segment["start_normal"] * offset
            end = segment["end"] + segment["end_normal"] * offset
            coords.extend((start, end))
        batch = batch_for_shader(shader, "LINES", {"pos": coords})
        _store_batch_cache_entry(cache_key, batch)
    shader.bind()
    shader.uniform_float("viewportSize", (viewport[2], viewport[3]))
    shader.uniform_float("lineWidth", LINE_WIDTH)
    shader.uniform_float("color", color)
    batch.draw(shader)


def _get_bbox_world_corners(obj):
    matrix = obj.matrix_world
    return [matrix @ Vector(corner) for corner in obj.bound_box]


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
    return max_x - min_x, max_y - min_y


def _get_dynamic_point_size(context):
    region = getattr(context, "region", None)
    region_data = getattr(context, "region_data", None)
    view_layer = getattr(context, "view_layer", None)
    object_name = get_active_check_object_name(context)
    obj = view_layer.objects.get(object_name) if view_layer is not None and object_name else None
    if region is None or region_data is None or obj is None:
        return POINT_SIZE_MAX

    bounds = _get_screen_bounds(region, region_data, _get_bbox_world_corners(obj))
    if bounds is None:
        return POINT_SIZE_MAX

    width, height = bounds
    frame_size = min(width, height)
    return max(POINT_SIZE_MIN, min(POINT_SIZE_MAX, frame_size * POINT_SIZE_FACTOR))


def _draw_points(points, color, offset=0.0, point_size=POINT_SIZE_MAX, object_name="", payload_token=0):
    if not points:
        return

    points = _limit_payload(points, MAX_POINT_PRIMITIVES)
    shader = _get_point_shader()
    cache_key = _batch_cache_key("points", object_name, color, offset, len(points), payload_token, point_size=point_size)
    batch = DRAW_BATCH_CACHE.get(cache_key)
    if batch is None:
        coords = [point["point"] + point["normal"] * offset for point in points]
        batch = batch_for_shader(shader, "POINTS", {"pos": coords})
        _store_batch_cache_entry(cache_key, batch)
    gpu.state.program_point_size_set(True)
    gpu.state.point_size_set(point_size)
    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("size", point_size)
    batch.draw(shader)
    gpu.state.point_size_set(1.0)
    gpu.state.program_point_size_set(False)


def _draw_faces(faces, color, offset=0.0, object_name="", payload_token=0):
    if not faces:
        return

    faces = _limit_payload(faces, MAX_FACE_PRIMITIVES)
    shader = _get_face_shader()
    gpu.state.face_culling_set("NONE")
    cache_key = _batch_cache_key("faces", object_name, color, offset, len(faces), payload_token)
    batches = DRAW_BATCH_CACHE.get(cache_key)
    if batches is None:
        batches = []
        for face in faces:
            coords = [vert + (face["normal"] * offset) for vert in face["verts"]]
            indices = face.get("indices") or []
            if len(coords) < 3:
                continue
            batches.append(batch_for_shader(shader, "TRIS", {"pos": coords}, indices=indices))
        _store_batch_cache_entry(cache_key, batches)

    shader.bind()
    shader.uniform_float("color", color)
    for batch in batches:
        batch.draw(shader)
    gpu.state.face_culling_set("NONE")


def _draw_overlay_for_settings(context, data):
    definitions = get_visible_check_definitions(context)
    prefs = get_prefs()
    if prefs is None:
        return
    point_size = _get_dynamic_point_size(context)
    object_name = get_active_check_object_name(context)
    payload_token = data.get("_batch_signature") if isinstance(data, dict) else None
    if payload_token is None:
        payload_token = id(data)

    for definition in definitions:
        color = tuple(getattr(prefs, definition["pref_color_prop"]))
        offset = getattr(prefs, definition["pref_offset_prop"])
        payload = data.get(definition["payload_key"])
        extra_face_payload = data.get(definition["extra_face_payload_key"]) if definition.get("extra_face_payload_key") else None
        if definition["draw_kind"] == "segments":
            if extra_face_payload:
                _draw_faces(extra_face_payload, color, offset, object_name=object_name, payload_token=payload_token)
            _draw_segments(payload, color, offset, object_name=object_name, payload_token=payload_token)
        elif definition["draw_kind"] == "points":
            if extra_face_payload:
                _draw_faces(extra_face_payload, color, offset, object_name=object_name, payload_token=payload_token)
            _draw_points(
                payload,
                color,
                offset,
                point_size=point_size,
                object_name=object_name,
                payload_token=payload_token,
            )
        elif definition["draw_kind"] == "faces":
            _draw_faces(payload, color, offset, object_name=object_name, payload_token=payload_token)


def draw_callback_view():
    context = bpy.context
    if context is None:
        return

    scene = getattr(context, "scene", None)
    settings = getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None
    if settings is None or settings.mode != "CHECK" or not settings.show_overlay:
        return

    if not is_meshcheck_owner_context(context):
        return

    if getattr(context, "mode", "") == 'EDIT_MESH':
        data = get_edit_mode_active_check_overlay_data(context)
    else:
        data = get_active_check_overlay_data(context)
    if not data:
        return

    _begin_overlay_depth_state(context)
    _draw_overlay_for_settings(context, data)
    _end_overlay_depth_state()
