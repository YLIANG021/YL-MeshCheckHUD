import os

import bpy.utils.previews


CHECK_ICON_FILES = {
    "NGONS": "check_01.png",
    "DOUBLES": "check_02.png",
    "ISOLATED_VERTS": "check_03.png",
    "LONG_TRIS": "check_04.png",
    "TINY_FACES": "check_05.png",
    "POLES": "check_06.png",
    "NON_MANIFOLD": "check_07.png",
    "MISSING_SHARP": "check_08.png",
    "OFF": "check_off.png",
}

ICON_FALLBACKS = {
    "NGONS": "BLANK1",
    "DOUBLES": "BLANK1",
    "ISOLATED_VERTS": "BLANK1",
    "LONG_TRIS": "BLANK1",
    "TINY_FACES": "BLANK1",
    "POLES": "BLANK1",
    "NON_MANIFOLD": "BLANK1",
    "MISSING_SHARP": "BLANK1",
    "OFF": "MATPLANE",
}

_icon_collection = None


def _icons_dir():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "icons"))


def register():
    global _icon_collection
    collection = bpy.utils.previews.new()
    icons_dir = _icons_dir()
    for key, filename in CHECK_ICON_FILES.items():
        path = os.path.join(icons_dir, filename)
        if os.path.isfile(path):
            collection.load(key, path, 'IMAGE')
    _icon_collection = collection


def unregister():
    global _icon_collection
    if _icon_collection is not None:
        bpy.utils.previews.remove(_icon_collection)
        _icon_collection = None


def get_check_icon_value(check_id, enabled=True):
    key = check_id if enabled else "OFF"
    if _icon_collection is None:
        return 0
    preview = _icon_collection.get(key)
    return preview.icon_id if preview is not None else 0


def get_check_icon_fallback(check_id, enabled=True):
    del check_id
    return "BLANK1" if enabled else ICON_FALLBACKS["OFF"]
