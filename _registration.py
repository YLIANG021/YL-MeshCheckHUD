# SPDX-License-Identifier: GPL-3.0-or-later

import bpy


def safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError:
        pass


def unregister_classes(classes):
    for cls in reversed(classes):
        safe_unregister_class(cls)


def register_classes(classes):
    registered_classes = []
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
            registered_classes.append(cls)
    except Exception:
        unregister_classes(registered_classes)
        raise
    return registered_classes
