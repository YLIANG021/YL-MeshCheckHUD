import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, FloatVectorProperty

from .core import ADDON_PACKAGE, tag_update_dirty
from ..i18n import pgettext
from ..meshcheck.definitions import CHECK_DEFINITIONS


class RTD_Preferences(bpy.types.AddonPreferences):
    """Add-on preferences."""

    bl_idname = ADDON_PACKAGE

    meshcheck_ngons_color: FloatVectorProperty(
        name="Ngons Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(1.0, 0.01032982303, 0.001517634918, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_ngons_offset: FloatProperty(
        name="Ngons Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_doubles_color: FloatVectorProperty(
        name="Doubles Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(1.0, 0.165132194502, 0.0, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_doubles_offset: FloatProperty(
        name="Doubles Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_poles_color: FloatVectorProperty(
        name="Poles Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.0, 0.223227957317, 0.964686247894, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_poles_offset: FloatProperty(
        name="Poles Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_isolated_color: FloatVectorProperty(
        name="Isolated Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(1.0, 0.871367119199, 0.0, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_isolated_offset: FloatProperty(
        name="Isolated Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_long_tris_color: FloatVectorProperty(
        name="Needle Tris Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.028426039504, 1.0, 0.0, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_long_tris_offset: FloatProperty(
        name="Needle Tris Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_tiny_faces_color: FloatVectorProperty(
        name="Tiny Faces Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.0, 0.863157213454, 0.938685728458, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_tiny_faces_offset: FloatProperty(
        name="Tiny Faces Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_non_manifold_color: FloatVectorProperty(
        name="Non-manifold Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.127437680436, 0.034339806809, 0.991102097114, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_non_manifold_offset: FloatProperty(
        name="Non-manifold Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_missing_sharp_color: FloatVectorProperty(
        name="Sharp Color",
        subtype="COLOR",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.752942216776, 0.08228270713, 0.991102097114, 0.8),
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_missing_sharp_offset: FloatProperty(
        name="Sharp Offset",
        default=0.00020,
        min=0.0,
        max=10.0,
        precision=5,
        update=lambda self, context: tag_update_dirty(),
    )

    enable_display: BoolProperty(
        name="Enable Text HUD",
        description="Enable the text HUD",
        default=True,
        update=lambda self, context: tag_update_dirty(),
    )

    use_axis_colors: BoolProperty(
        name="Use Axis Colors",
        description="Display each dimension using its axis color",
        default=True,
        update=lambda self, context: tag_update_dirty(),
    )

    show_units: BoolProperty(
        name="Show Units",
        description="Show units next to dimension values",
        default=True,
        update=lambda self, context: tag_update_dirty(),
    )

    auto_unit: BoolProperty(
        name="Auto Unit (m/cm)",
        description="Automatically switch between meters and centimeters based on object size",
        default=False,
        update=lambda self, context: tag_update_dirty(),
    )

    unit_system: EnumProperty(
        name="Unit System",
        description="Choose the unit system used for displayed dimensions",
        items=[
            ("m", "Meters", "Display dimensions in meters"),
            ("cm", "Centimeters", "Display dimensions in centimeters"),
            ("mm", "Millimeters", "Display dimensions in millimeters"),
        ],
        default="m",
        update=lambda self, context: tag_update_dirty(),
    )

    font_size: IntProperty(
        name="Font Size",
        description="Set the overlay font size",
        default=16,
        min=8,
        max=64,
        update=lambda self, context: tag_update_dirty(),
    )

    show_unapplied_scale: BoolProperty(
        name="Show Unapplied Scale Warning",
        description="Show the unapplied scale warning in the status line",
        default=True,
        update=lambda self, context: tag_update_dirty(),
    )

    show_high_poly_threshold: BoolProperty(
        name="Show Face Count Threshold",
        description="Show the active face count threshold in the status line",
        default=True,
        update=lambda self, context: tag_update_dirty(),
    )

    high_poly_face_limit: IntProperty(
        name="Face Count Threshold",
        description="Face count threshold used before edit-mode stats simplify",
        default=100000,
        min=50000,
        max=1000000,
        step=10000,
        update=lambda self, context: tag_update_dirty(),
    )

    meshcheck_edit_realtime_tri_limit: IntProperty(
        name="Realtime Check Triangle Limit",
        description="In edit mode, active check overlay refresh stays realtime up to this triangle count and switches to debounced refresh above it",
        default=25000,
        min=10000,
        max=100000,
        step=1000,
        update=lambda self, context: tag_update_dirty(),
    )

    enable_background: BoolProperty(
        name="Enable Background",
        description="Draw a background behind the overlay text",
        default=True,
        update=lambda self, context: tag_update_dirty(),
    )

    background_opacity: IntProperty(
        name="Background Opacity",
        description="Set background opacity",
        default=50,
        min=0,
        max=100,
        subtype="PERCENTAGE",
        update=lambda self, context: tag_update_dirty(),
    )

    ui_position: EnumProperty(
        name="UI Position",
        description="Choose where the overlay is drawn in the viewport",
        items=[
            ("RB", "Right Bottom", "Draw the overlay in the lower-right corner"),
            ("LB", "Left Bottom", "Draw the overlay in the lower-left corner"),
            ("RT", "Right Top", "Draw the overlay in the upper-right corner"),
            ("LT", "Left Top", "Draw the overlay in the upper-left corner"),
        ],
        default="RB",
        update=lambda self, context: tag_update_dirty(),
    )

    ui_x_offset: IntProperty(
        name="X Offset",
        description="Horizontal offset from the selected corner",
        default=45,
        min=0,
        update=lambda self, context: tag_update_dirty(),
    )

    ui_y_offset: IntProperty(
        name="Y Offset",
        description="Vertical offset from the selected corner",
        default=15,
        min=0,
        update=lambda self, context: tag_update_dirty(),
    )

    prefs_tab: EnumProperty(
        name="Section",
        items=[
            ("DISPLAY", "Display", "HUD display settings"),
            ("PERFORMANCE", "Performance", "Performance settings"),
            ("MESHCHECK", "Mesh Check", "Mesh check style settings"),
        ],
        default="DISPLAY",
    )

    def _draw_display_box(self, layout):
        t = pgettext
        header_row = layout.row(align=True)
        header_row.prop(self, "enable_display", text=t("Enable Text HUD"))
        header_row.prop(self, "font_size", text=t("Font Size"))

        content = layout.column(align=True)
        content.enabled = self.enable_display

        options_row = content.row(align=True)
        options_row.prop(self, "use_axis_colors", text=t("Use Axis Colors"))
        options_row.prop(self, "show_unapplied_scale", text=t("Show Unapplied Scale Warning"))

        content.separator()
        units_box = content.column(align=True)
        units_box.label(text=t("Units"))
        units_row = units_box.row(align=True)
        units_row.prop(self, "show_units", text=t("Show Units"))
        auto_unit_row = units_row.row(align=True)
        auto_unit_row.enabled = self.show_units
        auto_unit_row.prop(self, "auto_unit", text=t("Auto Unit (m/cm)"))

        unit_picker = units_box.row(align=True)
        unit_picker.enabled = self.show_units and not self.auto_unit
        unit_picker.prop(self, "unit_system", expand=True)

        content.separator()
        position_box = content.column(align=True)
        position_box.label(text=t("Position Settings"))
        position_grid = position_box.grid_flow(
            row_major=True,
            columns=2,
            even_columns=True,
            even_rows=True,
            align=True,
        )
        position_grid.prop_enum(self, "ui_position", "LT", text=t("Left Top"))
        position_grid.prop_enum(self, "ui_position", "RT", text=t("Right Top"))
        position_grid.prop_enum(self, "ui_position", "LB", text=t("Left Bottom"))
        position_grid.prop_enum(self, "ui_position", "RB", text=t("Right Bottom"))

        offset_row = position_box.row(align=True)
        offset_row.prop(self, "ui_x_offset", text=t("X Offset"))
        offset_row.prop(self, "ui_y_offset", text=t("Y Offset"))

        content.separator()
        background_box = content.column(align=True)
        background_box.label(text=t("Background"))
        background_box.prop(self, "enable_background", text=t("Enable Background"))
        opacity_row = background_box.row()
        opacity_row.enabled = self.enable_background
        opacity_row.prop(self, "background_opacity", text=t("Background Opacity"), slider=True)

    def _draw_performance_box(self, layout):
        t = pgettext
        threshold_row = layout.row(align=True)
        threshold_row.prop(self, "show_high_poly_threshold", text=t("Show Face Count Threshold"))
        limit_row = threshold_row.row(align=True)
        limit_row.enabled = self.show_high_poly_threshold
        limit_row.prop(self, "high_poly_face_limit", text=t("Face Count Threshold"))

        realtime_row = layout.row(align=True)
        realtime_row.prop(
            self,
            "meshcheck_edit_realtime_tri_limit",
            text=t("Realtime Check Triangle Limit"),
        )

    def _draw_meshcheck_styles_box(self, layout):
        t = pgettext
        styles_grid = layout.grid_flow(
            row_major=True,
            columns=2,
            even_columns=True,
            even_rows=True,
            align=True,
        )
        for definition in CHECK_DEFINITIONS:
            item_box = styles_grid.box()
            item_box.use_property_split = False
            item_box.use_property_decorate = False

            split = item_box.split(factor=0.28, align=True)
            name_col = split.column(align=True)
            name_col.label(text=definition["label"])

            value_col = split.column(align=True)
            color_row = value_col.row(align=True)
            color_row.prop(self, definition["pref_color_prop"], text=t("Color"))

            offset_row = value_col.row(align=True)
            offset_row.prop(self, definition["pref_offset_prop"], text=t("Offset"))

    def _draw_tab_bar(self, layout):
        t = pgettext
        row = layout.row(align=True)
        row.prop_enum(self, "prefs_tab", "DISPLAY", text=t("Display"))
        row.prop_enum(self, "prefs_tab", "PERFORMANCE", text=t("Performance"))
        row.prop_enum(self, "prefs_tab", "MESHCHECK", text=t("Mesh Check"))

    def _draw_section_body(self, layout, title, draw_fn, compact=False):
        box = layout.box()
        box.use_property_split = False
        box.use_property_decorate = False

        title_row = box.row()
        title_row.enabled = False
        title_row.label(text=title)

        body = box.column(align=True)
        draw_fn(body)

    def _draw_active_tab(self, layout):
        t = pgettext
        if self.prefs_tab == "DISPLAY":
            self._draw_section_body(layout, t("Display"), self._draw_display_box)
        elif self.prefs_tab == "PERFORMANCE":
            self._draw_section_body(layout, t("Performance"), self._draw_performance_box)
        else:
            self._draw_section_body(layout, t("Mesh Check"), self._draw_meshcheck_styles_box, compact=True)

    def draw(self, context):
        del context
        t = pgettext

        layout = self.layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        header = layout.box()
        header.label(text="YL MeshCheckHUD")

        subtitle = header.row()
        subtitle.enabled = False
        subtitle.label(
            text=t("Show live triangle count and overall dimensions for the current mesh selection."),
        )

        content = layout.column()
        self._draw_tab_bar(content)
        self._draw_active_tab(content)
