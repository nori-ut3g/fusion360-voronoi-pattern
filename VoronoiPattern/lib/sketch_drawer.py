"""
Draw Voronoi pattern cells onto a Fusion 360 sketch.

All computation is done in sketch space (cm).
Boundary extraction converts model-space points to sketch-space
using sketch.modelToSketchSpace().
"""

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    # Allow import outside Fusion for testing
    adsk = None

def _simplify_cell(cell, min_edge_len):
    """Remove vertices that create edges shorter than min_edge_len.

    When boundary clipping creates tiny edges, they split what should
    be a single corner into two vertices. Merging them back produces
    cleaner geometry for filleting.

    Uses a two-pass linear algorithm instead of iterative while-loop
    to avoid O(n^2) behavior with many short edges.
    """
    n = len(cell)
    if n < 4:
        return list(cell)

    threshold_sq = min_edge_len * min_edge_len

    # Pass 1: mark vertices to remove (skip vertex j when edge i->j is short)
    keep = [True] * n
    removed = 0
    for i in range(n):
        if not keep[i]:
            continue
        j = (i + 1) % n
        if not keep[j]:
            continue
        x1, y1 = cell[i]
        x2, y2 = cell[j]
        if (x2 - x1) ** 2 + (y2 - y1) ** 2 < threshold_sq:
            if n - removed > 3:
                keep[j] = False
                removed += 1

    result = [cell[i] for i in range(n) if keep[i]]

    # Pass 2: handle wrap-around edge (last -> first) that pass 1 may miss
    if len(result) > 3:
        x1, y1 = result[-1]
        x2, y2 = result[0]
        if (x2 - x1) ** 2 + (y2 - y1) ** 2 < threshold_sq:
            result.pop()

    return result if len(result) >= 3 else list(cell)


def draw_voronoi_pattern(sketch, cells, corner_radius):
    """Draw Voronoi hole pattern on an existing sketch.

    Args:
        sketch: Fusion 360 Sketch object (already created on the target face).
        cells: List of Voronoi cell polygons (list of (x, y) tuples in cm).
        corner_radius: Corner rounding radius in cm (0 for sharp corners).
    """
    from lib.polygon import round_corners

    sketch.isComputeDeferred = True
    try:
        for cell in cells:
            if len(cell) < 3:
                continue

            if corner_radius > 0:
                cell = _simplify_cell(cell, max(corner_radius, 0.01))
                if len(cell) < 3:
                    continue
                segments = round_corners(cell, corner_radius)
                _draw_segments(sketch, segments)
            else:
                _draw_straight_cell(sketch, cell)
    finally:
        sketch.isComputeDeferred = False


def _draw_segments(sketch, segments):
    """Draw a cell from pre-computed line/arc segments.

    Uses addByTwoPoints for lines and addByThreePoints for arcs,
    avoiding addFillet which corrupts SWIG wrappers.
    Falls back to straight lines when arcs fail to ensure closed profiles.
    """
    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs
    # Cache Point3D.create to avoid repeated attribute lookups
    create_pt = adsk.core.Point3D.create

    for seg in segments:
        if seg['type'] == 'line':
            dx = seg['x2'] - seg['x1']
            dy = seg['y2'] - seg['y1']
            if dx * dx + dy * dy < 1e-10:
                continue
            lines.addByTwoPoints(
                create_pt(seg['x1'], seg['y1'], 0),
                create_pt(seg['x2'], seg['y2'], 0))
        elif seg['type'] == 'arc':
            x1, y1 = seg['x1'], seg['y1']
            mx, my = seg['mx'], seg['my']
            x2, y2 = seg['x2'], seg['y2']
            d12 = (x2 - x1) ** 2 + (y2 - y1) ** 2
            if d12 < 1e-10:
                continue
            # Check for degenerate arc (collinear points)
            cross = (mx - x1) * (y2 - y1) - (my - y1) * (x2 - x1)
            if abs(cross) < 1e-8:
                # Nearly straight — draw as line
                lines.addByTwoPoints(
                    create_pt(x1, y1, 0), create_pt(x2, y2, 0))
                continue
            pt1 = create_pt(x1, y1, 0)
            mid = create_pt(mx, my, 0)
            pt2 = create_pt(x2, y2, 0)
            arc = arcs.addByThreePoints(pt1, mid, pt2)
            if arc is None:
                # Arc creation failed — fall back to straight line
                lines.addByTwoPoints(pt1, pt2)


def _draw_straight_cell(sketch, cell):
    """Draw a cell as a closed polyline (straight edges only)."""
    lines = sketch.sketchCurves.sketchLines
    create_pt = adsk.core.Point3D.create
    n = len(cell)
    for i in range(n):
        x1, y1 = cell[i]
        x2, y2 = cell[(i + 1) % n]
        lines.addByTwoPoints(create_pt(x1, y1, 0), create_pt(x2, y2, 0))


def get_face_boundary(face, sketch):
    """Extract the outer boundary polygon from a BRepFace in sketch space.

    Args:
        face: adsk.fusion.BRepFace
        sketch: adsk.fusion.Sketch created on the face.

    Returns:
        List of (x, y) tuples in sketch-space cm.
    """
    # Find the outer loop (face.loops[0] may be a hole loop)
    outer_loop = None
    for loop in face.loops:
        if loop.isOuter:
            outer_loop = loop
            break
    if outer_loop is None:
        outer_loop = face.loops[0]

    boundary_points = []

    for edge in outer_loop.edges:
        evaluator = edge.evaluator
        _, start_param, end_param = evaluator.getParameterExtents()
        _, points = evaluator.getStrokes(start_param, end_param, 0.01)
        for pt in points:
            # Convert from model space to sketch space
            sketch_pt = sketch.modelToSketchSpace(pt)
            boundary_points.append((sketch_pt.x, sketch_pt.y))

    # Remove duplicate consecutive points
    cleaned = [boundary_points[0]]
    for i in range(1, len(boundary_points)):
        px, py = boundary_points[i]
        lx, ly = cleaned[-1]
        if abs(px - lx) > 0.0001 or abs(py - ly) > 0.0001:
            cleaned.append((px, py))

    return cleaned


def get_face_holes(face, sketch):
    """Extract inner loop (hole) polygons from a BRepFace in sketch space.

    Args:
        face: adsk.fusion.BRepFace
        sketch: adsk.fusion.Sketch created on the face.

    Returns:
        List of hole polygons, each a list of (x, y) tuples in sketch-space cm.
    """
    holes = []
    for loop in face.loops:
        if loop.isOuter:
            continue

        hole_points = []
        for edge in loop.edges:
            evaluator = edge.evaluator
            _, start_param, end_param = evaluator.getParameterExtents()
            _, points = evaluator.getStrokes(start_param, end_param, 0.01)
            for pt in points:
                sketch_pt = sketch.modelToSketchSpace(pt)
                hole_points.append((sketch_pt.x, sketch_pt.y))

        if not hole_points:
            continue

        # Remove duplicate consecutive points
        cleaned = [hole_points[0]]
        for i in range(1, len(hole_points)):
            px, py = hole_points[i]
            lx, ly = cleaned[-1]
            if abs(px - lx) > 0.0001 or abs(py - ly) > 0.0001:
                cleaned.append((px, py))

        if len(cleaned) >= 3:
            holes.append(cleaned)

    return holes


def get_exclude_circles(selections, sketch):
    """Extract exclusion circles from selected circular edges.

    Args:
        selections: List of selected entities (BRepEdge).
        sketch: adsk.fusion.Sketch for coordinate conversion.

    Returns:
        List of (cx, cy, radius) tuples in sketch-space cm.
    """
    circles = []
    for entity in selections:
        if hasattr(entity, 'geometry'):
            geom = entity.geometry
            if hasattr(geom, 'center') and hasattr(geom, 'radius'):
                center_3d = adsk.core.Point3D.create(
                    geom.center.x, geom.center.y, geom.center.z)
                sketch_center = sketch.modelToSketchSpace(center_3d)
                circles.append((sketch_center.x, sketch_center.y, geom.radius))
    return circles
