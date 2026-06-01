# SPDX-License-Identifier: GPL-3.0-or-later

from . import analysis_hud, heatmap, i18n, meshcheck, overlay, ui


MODULES = (
    overlay,
    heatmap,
    meshcheck,
    analysis_hud,
    ui,
)


def _safe_unregister_module(module):
    try:
        module.unregister()
    except Exception:
        pass


def register():
    """Register the extension."""
    registered_modules = []
    active_module = None
    try:
        for module in MODULES:
            active_module = module
            module.register()
            registered_modules.append(module)
            active_module = None
        i18n.register()
    except Exception:
        try:
            i18n.unregister()
        except Exception:
            pass
        if active_module is not None:
            _safe_unregister_module(active_module)
        for module in reversed(registered_modules):
            _safe_unregister_module(module)
        raise


def unregister():
    """Unregister the extension."""
    try:
        i18n.unregister()
    except Exception:
        pass
    for module in reversed(MODULES):
        _safe_unregister_module(module)


if __name__ == "__main__":
    register()
