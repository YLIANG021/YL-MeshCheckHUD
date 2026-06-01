def count_mesh_triangles(mesh):
    if mesh is None:
        return 0

    if not getattr(mesh, "loop_triangles", None):
        try:
            mesh.calc_loop_triangles()
        except (AttributeError, RuntimeError, ValueError):
            return sum(len(poly.vertices) - 2 for poly in mesh.polygons)

    return len(mesh.loop_triangles)


def get_evaluated_mesh_data(obj, depsgraph):
    try:
        eval_obj = obj.evaluated_get(depsgraph)
        return eval_obj, eval_obj.data
    except (AttributeError, ReferenceError, RuntimeError):
        try:
            return obj, obj.data
        except (AttributeError, ReferenceError, RuntimeError):
            return None, None


def get_evaluated_object_triangle_count(obj, depsgraph):
    eval_obj, mesh = get_evaluated_mesh_data(obj, depsgraph)
    if eval_obj is None or mesh is None:
        return 0
    return count_mesh_triangles(mesh)
