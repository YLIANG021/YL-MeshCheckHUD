# SPDX-License-Identifier: GPL-3.0-or-later

from . import analysis_hud, heatmap, i18n, meshcheck, overlay, ui


def register():
    """Register the extension."""
    overlay.register()
    heatmap.register()
    meshcheck.register()
    analysis_hud.register()
    ui.register()
    i18n.register()


def unregister():
    """Unregister the extension."""
    i18n.unregister()
    ui.unregister()
    analysis_hud.unregister()
    meshcheck.unregister()
    heatmap.unregister()
    overlay.unregister()


if __name__ == "__main__":
    register()
