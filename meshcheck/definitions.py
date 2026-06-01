CHECK_DEFINITIONS = (
    {
        "id": "NGONS",
        "label": "Ngons",
        "name": "Ngons",
        "show_prop": "show_ngons",
        "display_prop": "show_ngons_column",
        "count_attr": "ngon_count",
        "draw_kind": "faces",
        "payload_key": "ngon_faces",
        "pref_color_prop": "meshcheck_ngons_color",
        "pref_offset_prop": "meshcheck_ngons_offset",
    },
    {
        "id": "DOUBLES",
        "label": "Doubles",
        "name": "Doubles",
        "show_prop": "show_doubles",
        "display_prop": "show_doubles_column",
        "count_attr": "double_vert_count",
        "draw_kind": "points",
        "payload_key": "double_points",
        "pref_color_prop": "meshcheck_doubles_color",
        "pref_offset_prop": "meshcheck_doubles_offset",
    },
    {
        "id": "ISOLATED_VERTS",
        "label": "Isolated",
        "name": "Isolated Verts",
        "show_prop": "show_isolated_verts",
        "display_prop": "show_isolated_verts_column",
        "count_attr": "isolated_vert_count",
        "draw_kind": "points",
        "payload_key": "isolated_points",
        "pref_color_prop": "meshcheck_isolated_color",
        "pref_offset_prop": "meshcheck_isolated_offset",
    },
    {
        "id": "LONG_TRIS",
        "label": "Needle Tris",
        "name": "Needle Tris",
        "show_prop": "show_long_tris",
        "display_prop": "show_long_tris_column",
        "count_attr": "long_tri_count",
        "draw_kind": "segments",
        "payload_key": "long_tri_segments",
        "extra_face_payload_key": "long_tri_faces",
        "pref_color_prop": "meshcheck_long_tris_color",
        "pref_offset_prop": "meshcheck_long_tris_offset",
    },
    {
        "id": "TINY_FACES",
        "label": "Tiny Faces",
        "name": "Tiny Faces",
        "show_prop": "show_tiny_faces",
        "display_prop": "show_tiny_faces_column",
        "count_attr": "tiny_face_count",
        "draw_kind": "points",
        "payload_key": "tiny_face_points",
        "extra_face_payload_key": "tiny_face_faces",
        "pref_color_prop": "meshcheck_tiny_faces_color",
        "pref_offset_prop": "meshcheck_tiny_faces_offset",
    },
    {
        "id": "POLES",
        "label": "Poles",
        "name": "Poles",
        "show_prop": "show_poles",
        "display_prop": "show_poles_column",
        "count_attr": "pole_count",
        "draw_kind": "points",
        "payload_key": "pole_points",
        "pref_color_prop": "meshcheck_poles_color",
        "pref_offset_prop": "meshcheck_poles_offset",
    },
    {
        "id": "NON_MANIFOLD",
        "label": "Non-manifold",
        "name": "Non-manifold",
        "show_prop": "show_non_manifold",
        "display_prop": "show_non_manifold_column",
        "count_attr": "non_manifold_count",
        "draw_kind": "segments",
        "payload_key": "non_manifold_segments",
        "pref_color_prop": "meshcheck_non_manifold_color",
        "pref_offset_prop": "meshcheck_non_manifold_offset",
    },
    {
        "id": "MISSING_SHARP",
        "label": "Sharp",
        "name": "Sharp",
        "show_prop": "show_missing_sharp",
        "display_prop": "show_missing_sharp_column",
        "count_attr": "missing_sharp_edge_count",
        "draw_kind": "segments",
        "payload_key": "missing_sharp_segments",
        "pref_color_prop": "meshcheck_missing_sharp_color",
        "pref_offset_prop": "meshcheck_missing_sharp_offset",
    },
)


CHECKS_BY_ID = {item["id"]: item for item in CHECK_DEFINITIONS}
DEFAULT_CHECK_ID = "NGONS"


def get_check_definition(check_id, fallback=DEFAULT_CHECK_ID):
    definition = CHECKS_BY_ID.get(check_id)
    if definition is not None:
        return definition
    if fallback is None:
        return None
    return CHECKS_BY_ID[fallback]
