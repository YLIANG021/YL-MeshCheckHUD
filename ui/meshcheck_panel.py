import bpy

from ..heatmap.logic import is_heatmap_active
from ..i18n import pgettext
from ..meshcheck.core import format_material_slot_value
from ..meshcheck.definitions import CHECK_DEFINITIONS, get_check_definition
from .check_detail import draw_check_detail, get_check_detail_title, should_draw_check_detail
from .icons import get_check_icon_fallback, get_check_icon_value

translate = bpy.app.translations.pgettext_iface


PREVIEW_COLUMNS = (
    ("NAME", "Object", 0.28),
    ("TRIS", "Tris", 0.20),
    ("RATIO", "%", 0.20),
    ("MATS", "Mats/Slots", 0.16),
    ("UVS", "UVs", 0.16),
)


def _all_check_visibility_enabled(settings):
    return all(getattr(settings, definition["show_prop"], False) for definition in CHECK_DEFINITIONS)


def _columns_are_even(columns, tolerance=1e-6):
    if len(columns) <= 1:
        return False
    widths = [width for _column_id, _label, width in columns]
    first_width = widths[0]
    return all(abs(width - first_width) <= tolerance for width in widths[1:])


def _draw_split_cells(container, columns, draw_cell):
    if _columns_are_even(columns):
        # Use a true equal-width grid for icon rows so narrow sidebars do not
        # accumulate split rounding error and overflow the right-most buttons.
        grid = container.grid_flow(
            row_major=True,
            columns=len(columns),
            even_columns=True,
            even_rows=True,
            align=True,
        )
        for index, (column_id, _label, _width) in enumerate(columns):
            cell = grid.row(align=True)
            draw_cell(cell, column_id, index)
        return

    current = container
    remaining = 1.0
    for index, (column_id, _label, width) in enumerate(columns):
        if index == len(columns) - 1:
            cell = current.row(align=True)
            draw_cell(cell, column_id, index)
            break
        factor = width / remaining if remaining > 0 else width
        split = current.split(factor=factor, align=True)
        cell = split.row(align=True)
        draw_cell(cell, column_id, index)
        current = split
        remaining -= width


def _sort_icon(active_sort_by, column_id, sort_descending):
    if active_sort_by != column_id:
        return 'NONE'
    return 'TRIA_DOWN' if sort_descending else 'TRIA_UP'


def _compact_button_scale(column_count):
    region = getattr(bpy.context, "region", None)
    region_width = getattr(region, "width", 0)
    if region_width <= 0 or column_count <= 0:
        return 1.0

    # Reserve some space for panel padding and split borders, then compress
    # icon buttons progressively as the available width per column shrinks.
    usable_width = max(region_width - 48, 1)
    width_per_column = usable_width / column_count
    if width_per_column >= 78:
        return 1.0
    if width_per_column >= 64:
        return 0.92
    if width_per_column >= 54:
        return 0.84
    if width_per_column >= 46:
        return 0.76
    return 0.68


def _icon_prop(cell, data, prop_name, enabled, check_id):
    icon_value = get_check_icon_value(check_id, enabled)
    if icon_value:
        cell.prop(
            data,
            prop_name,
            text=" ",
            icon_value=icon_value,
            toggle=True,
            emboss=True,
        )
    else:
        cell.prop(
            data,
            prop_name,
            text=" ",
            icon=get_check_icon_fallback(check_id, enabled),
            toggle=True,
            emboss=True,
        )


def _draw_scope_picker(container, settings):
    row = container.row(align=True)
    row.use_property_split = False
    row.prop(settings, "scope", text="")


def _draw_table_header(container, columns, settings, sort_attr, descending_attr):
    row = container.row(align=True)
    row.enabled = getattr(bpy.context, "mode", None) == 'OBJECT'
    active_sort_by = getattr(settings, sort_attr)
    sort_descending = getattr(settings, descending_attr)

    def draw_cell(cell, column_id, col_index):
        del col_index
        label = translate(next(label for key, label, _width in columns if key == column_id))
        is_active = active_sort_by == column_id
        op = cell.operator(
            "yl_omnihud.sort_meshcheck_results",
            text=label,
            icon=_sort_icon(active_sort_by, column_id, sort_descending),
            depress=is_active,
        )
        op.sort_by = column_id

    _draw_split_cells(row, columns, draw_cell)


def _check_columns(settings):
    visible_checks = [
        item
        for item in CHECK_DEFINITIONS
        if getattr(settings, item.get("display_prop", ""), True)
    ]
    column_width = 1.0 / (len(visible_checks) + 1) if visible_checks else 1.0
    columns = [("NAME", translate("Object"), column_width)]
    for item in visible_checks:
        columns.append((item["id"], translate(item["label"]), column_width))
    return tuple(columns)


def _draw_check_picker(container, settings):
    row = container.row(align=True)
    row.enabled = getattr(bpy.context, "mode", None) == 'OBJECT'
    columns = _check_columns(settings)

    def draw_cell(cell, column_id, col_index):
        del col_index
        if column_id == "NAME":
            label = translate("Object")
            enabled = True
        else:
            definition = get_check_definition(column_id)
            label = (
                f'{translate("Poles")} > {settings.pole_threshold}'
                if column_id == "POLES"
                else f'{pgettext("Sharp")} > {settings.missing_sharp_angle:g}\N{DEGREE SIGN}'
                if column_id == "MISSING_SHARP"
                else translate(definition["label"])
            )
            enabled = getattr(settings, definition["show_prop"], False)
        cell.enabled = enabled
        op = cell.operator(
            "yl_omnihud.sort_meshcheck_results",
            text=label,
            icon=_sort_icon(settings.check_sort_by, column_id, settings.check_sort_descending),
        )
        op.sort_by = column_id

    _draw_split_cells(row, columns, draw_cell)


def _draw_check_visibility_toggles(container, settings):
    row = container.row(align=True)
    columns = _check_columns(settings)
    row.scale_x = _compact_button_scale(len(columns))

    def draw_cell(cell, column_id, col_index):
        del col_index
        if column_id == "NAME":
            all_enabled = _all_check_visibility_enabled(settings)
            has_enabled = any(getattr(settings, definition["show_prop"], False) for definition in CHECK_DEFINITIONS)
            has_restore_state = bool(settings.check_visibility_restore_state)
            icon = 'HIDE_OFF' if all_enabled else 'LOOP_BACK' if has_restore_state and not has_enabled else 'HIDE_ON'
            op = cell.operator(
                "yl_omnihud.toggle_all_check_visibility",
                text=" ",
                icon=icon,
                depress=all_enabled,
            )
            del op
            return

        definition = get_check_definition(column_id)
        enabled = getattr(settings, definition["show_prop"], False)
        _icon_prop(cell, settings, definition["show_prop"], enabled, column_id)

    _draw_split_cells(row, columns, draw_cell)


def _draw_advanced_settings(container, settings):
    doubles_definition = get_check_definition("DOUBLES")
    long_tris_definition = get_check_definition("LONG_TRIS")
    tiny_faces_definition = get_check_definition("TINY_FACES")
    poles_definition = get_check_definition("POLES")
    missing_sharp_definition = get_check_definition("MISSING_SHARP")

    advanced_box = container.box()
    header = advanced_box.row(align=True)
    header.prop(
        settings,
        "show_advanced",
        text="Check Settings",
        emboss=False,
        icon='TRIA_DOWN' if settings.show_advanced else 'TRIA_RIGHT',
    )

    if not settings.show_advanced:
        return

    body = advanced_box.column(align=True)
    columns_row = body.grid_flow(
        row_major=True,
        columns=len(CHECK_DEFINITIONS),
        even_columns=True,
        even_rows=True,
        align=True,
    )
    columns_row.scale_x = _compact_button_scale(len(CHECK_DEFINITIONS))
    for definition in CHECK_DEFINITIONS:
        is_visible = getattr(settings, definition["display_prop"], True)
        cell = columns_row.row(align=True)
        _icon_prop(cell, settings, definition["display_prop"], is_visible, definition["id"])

    body.separator()
    body.use_property_split = True
    if (
        getattr(settings, doubles_definition["show_prop"], False)
        and getattr(settings, doubles_definition["display_prop"], False)
    ):
        body.row().prop(settings, "doubles_distance")

    if (
        getattr(settings, long_tris_definition["show_prop"], False)
        and getattr(settings, long_tris_definition["display_prop"], False)
    ):
        body.row().prop(settings, "long_tri_ratio_threshold")

    if (
        getattr(settings, tiny_faces_definition["show_prop"], False)
        and getattr(settings, tiny_faces_definition["display_prop"], False)
    ):
        body.row().prop(settings, "tiny_face_area_threshold")

    if (
        getattr(settings, poles_definition["show_prop"], False)
        and getattr(settings, poles_definition["display_prop"], False)
    ):
        body.row().prop(settings, "pole_threshold")

    if (
        getattr(settings, missing_sharp_definition["show_prop"], False)
        and getattr(settings, missing_sharp_definition["display_prop"], False)
    ):
        body.row().prop(settings, "missing_sharp_angle")
        body.row().prop(settings, "missing_sharp_skip_marked")


def _check_value(item, column_id, enabled=True):
    if not enabled:
        return "—"
    if column_id == "NGONS":
        return str(item.ngon_count)
    if column_id == "DOUBLES":
        return str(item.double_vert_count)
    if column_id == "ISOLATED_VERTS":
        return str(item.isolated_vert_count)
    if column_id == "LONG_TRIS":
        return str(item.long_tri_count)
    if column_id == "TINY_FACES":
        return str(item.tiny_face_count)
    if column_id == "POLES":
        return str(item.pole_count)
    if column_id == "NON_MANIFOLD":
        return str(item.non_manifold_count)
    if column_id == "MISSING_SHARP":
        return str(item.missing_sharp_edge_count)
    return ""


class YLOMNIHUD_UL_preview_results(bpy.types.UIList):
    bl_idname = "YLOMNIHUD_UL_preview_results"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        del context, data, icon, active_data, active_propname, index
        row = layout.row(align=True)

        def draw_cell(cell, column_id, col_index):
            del col_index
            cell.alignment = 'CENTER'
            if column_id == "NAME":
                cell.label(text=item.object_name, translate=False)
            elif column_id == "TRIS":
                cell.label(text=f"{item.tris:,}")
            elif column_id == "RATIO":
                cell.label(text=f"{item.ratio * 100.0:.1f}")
            elif column_id == "MATS":
                cell.label(text=format_material_slot_value(item))
            elif column_id == "UVS":
                cell.label(text=str(item.uv_count))

        _draw_split_cells(row, PREVIEW_COLUMNS, draw_cell)


class YLOMNIHUD_UL_check_results(bpy.types.UIList):
    bl_idname = "YLOMNIHUD_UL_check_results"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        del context, icon, active_data, active_propname, index
        row = layout.row(align=True)
        columns = _check_columns(data)

        def draw_cell(cell, column_id, col_index):
            del col_index
            if column_id == "NAME":
                cell.alignment = 'CENTER'
                cell.label(text=item.object_name, translate=False)
            else:
                definition = get_check_definition(column_id)
                enabled = getattr(data, definition["show_prop"], False)
                cell.alignment = 'CENTER'
                cell.label(text=_check_value(item, column_id, enabled=enabled))

        _draw_split_cells(row, columns, draw_cell)


class YLOMNIHUD_PT_meshcheck(bpy.types.Panel):
    bl_label = "Mesh Check"
    bl_idname = "YLOMNIHUD_PT_meshcheck"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "YL MeshCheckHUD"
    bl_parent_id = "YLOMNIHUD_PT_main"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        check_settings = context.scene.yl_omnihud_meshcheck
        hud_active = is_heatmap_active(context) or check_settings.show_overlay
        is_object_mode = getattr(context, "mode", "") == 'OBJECT'

        layout.use_property_split = False
        layout.use_property_decorate = False

        _draw_scope_picker(layout, check_settings)

        action_row = layout.row(align=True)
        action_row.scale_y = 1.6
        preview_button = action_row.row(align=True)
        preview_button.operator(
            "yl_omnihud.preview_meshcheck",
            text=translate("Preview"),
            icon='HIDE_OFF' if hud_active else 'HIDE_ON',
            depress=hud_active,
        )
        xray_button = action_row.row(align=True)
        xray_button.enabled = check_settings.mode == 'CHECK'
        xray_button.prop(
            check_settings,
            "check_use_xray",
            text="",
            icon='XRAY',
            toggle=True,
        )

        mode_row = layout.row(align=True)
        preview_mode_button = mode_row.row(align=True)
        preview_mode_button.enabled = hud_active
        preview_mode_button.prop_enum(
            check_settings,
            "mode",
            'PREVIEW',
            text=translate("Heatmap"),
        )

        check_mode_button = mode_row.row(align=True)
        check_mode_button.enabled = hud_active or (
            getattr(context, "mode", "") == 'EDIT_MESH' and check_settings.mode == 'PREVIEW'
        )
        check_mode_button.prop_enum(
            check_settings,
            "mode",
            'CHECK',
            text=translate("Check"),
        )

        if not hud_active:
            return

        if check_settings.mode == 'PREVIEW':
            box = layout.box()
            box.label(text=translate("Heatmap Results"))
            _draw_table_header(box, PREVIEW_COLUMNS, check_settings, "preview_sort_by", "preview_sort_descending")
            if check_settings.preview_results:
                box.template_list(
                    "YLOMNIHUD_UL_preview_results",
                    "",
                    check_settings,
                    "preview_results",
                    check_settings,
                    "active_preview_index",
                    rows=5,
                )
            else:
                box.label(text=translate("Enable HUD to generate results."), icon='INFO')
        else:
            box = layout.box()
            is_check_detail = should_draw_check_detail(context, check_settings)
            if is_check_detail:
                box.label(text=get_check_detail_title(context), translate=False)
            else:
                box.label(text=translate("Check Results"))
                _draw_check_picker(box, check_settings)
                _draw_check_visibility_toggles(box, check_settings)
            if is_check_detail:
                draw_check_detail(box, context, check_settings)
            elif check_settings.check_results:
                box.template_list(
                    "YLOMNIHUD_UL_check_results",
                    "",
                    check_settings,
                    "check_results",
                    check_settings,
                    "active_check_index",
                    rows=5,
                )
            else:
                box.label(text=translate("Enable HUD to generate results."), icon='INFO')
            _draw_advanced_settings(layout, check_settings)
