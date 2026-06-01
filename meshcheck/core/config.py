from ..definitions import CHECK_DEFINITIONS


DEFAULT_DOUBLE_EPSILON = 0.0001
DEFAULT_LONG_TRI_RATIO_THRESHOLD = 12.0
DEFAULT_TINY_FACE_AREA_THRESHOLD = 1e-5
DEFAULT_ZERO_FACE_AREA_EPSILON = 1e-12


def _resolve_enabled_ids(enabled_ids=None):
    if enabled_ids is None:
        enabled_ids = (definition["id"] for definition in CHECK_DEFINITIONS)
    return frozenset(enabled_ids)


def _meshcheck_settings_from_context(context):
    scene = getattr(context, "scene", None)
    return getattr(scene, "yl_omnihud_meshcheck", None) if scene is not None else None


def get_double_epsilon(context=None):
    settings = _meshcheck_settings_from_context(context)
    if settings is None:
        return DEFAULT_DOUBLE_EPSILON
    value = getattr(settings, "doubles_distance", DEFAULT_DOUBLE_EPSILON)
    return max(float(value), 1e-12)


def get_pole_threshold(context=None):
    settings = _meshcheck_settings_from_context(context)
    if settings is None:
        return 8
    value = getattr(settings, "pole_threshold", 8)
    return max(3, min(int(value), 20))


def get_missing_sharp_angle_radians(context=None):
    settings = _meshcheck_settings_from_context(context)
    if settings is None:
        return 1.5707963267948966
    return float(getattr(settings, "missing_sharp_angle", 90.0)) * 0.017453292519943295


def get_missing_sharp_skip_marked(context=None):
    settings = _meshcheck_settings_from_context(context)
    if settings is None:
        return False
    return bool(getattr(settings, "missing_sharp_skip_marked", False))


def get_long_tri_ratio_threshold(context=None):
    settings = _meshcheck_settings_from_context(context)
    if settings is None:
        return DEFAULT_LONG_TRI_RATIO_THRESHOLD
    value = getattr(settings, "long_tri_ratio_threshold", DEFAULT_LONG_TRI_RATIO_THRESHOLD)
    return max(float(value), 1.0)


def get_tiny_face_area_threshold(context=None):
    settings = _meshcheck_settings_from_context(context)
    if settings is None:
        return DEFAULT_TINY_FACE_AREA_THRESHOLD
    value = getattr(settings, "tiny_face_area_threshold", DEFAULT_TINY_FACE_AREA_THRESHOLD)
    return max(float(value), 0.0)


def get_long_tri_degenerate_epsilon():
    return DEFAULT_ZERO_FACE_AREA_EPSILON


def _get_check_settings_signature(context=None):
    return (
        round(get_double_epsilon(context), 12),
        int(get_pole_threshold(context)),
        round(get_missing_sharp_angle_radians(context), 12),
        bool(get_missing_sharp_skip_marked(context)),
        round(get_long_tri_ratio_threshold(context), 6),
        round(get_tiny_face_area_threshold(context), 12),
    )


def get_enabled_check_ids(settings):
    if settings is None:
        return []

    enabled_ids = []
    for definition in CHECK_DEFINITIONS:
        if getattr(settings, definition["show_prop"], False):
            enabled_ids.append(definition["id"])
    return enabled_ids


def get_visible_check_ids(settings):
    if settings is None:
        return []

    visible_ids = []
    enabled_ids = set(get_enabled_check_ids(settings))
    for definition in CHECK_DEFINITIONS:
        if (
            definition["id"] in enabled_ids
            and getattr(settings, definition.get("display_prop", ""), True)
        ):
            visible_ids.append(definition["id"])
    return visible_ids


def get_visible_check_definitions(context):
    settings = _meshcheck_settings_from_context(context)
    if settings is None:
        return []

    visible_ids = set(get_visible_check_ids(settings))
    return [item for item in CHECK_DEFINITIONS if item["id"] in visible_ids]
