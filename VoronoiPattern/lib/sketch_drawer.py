"""
Draw Voronoi pattern cells onto a Fusion 360 sketch.

All input coordinates are in mm. Fusion 360 internal unit is cm,
so all coordinates are divided by 10 before drawing.
"""

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    # Allow import outside Fusion for testing
    adsk = None

from .polygon import round_corners


MM_TO_CM = 0.1  # 1mm = 0.1cm


def draw_voronoi_pattern(face, cells, corner_radius):
    """Draw Voronoi hole pattern on a Fusion 360 sketch.

    Args:
        face: BRepFace to create sketch on.
        cells: List of Voronoi cell polygons (list of (x, y) tuples in mm).
        corner_radius: Corner rounding radius in mm (0 for sharp corners).
    """
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    # Create sketch on the selected face
    sketch = root.sketches.add(face)

    # Group all drawing operations for undo
    design.timeline.timelineGroups.add(
        design.timeline.markerPosition - 1,
        design.timeline.markerPosition - 1,
    )

    for cell in cells:
        if len(cell) < 3:
            continue

        if corner_radius > 0:
            _draw_rounded_cell(sketch, cell, corner_radius)
        else:
            _draw_straight_cell(sketch, cell)


def _draw_straight_cell(sketch, cell):
    """Draw a cell as a closed polyline (straight edges only)."""
    lines = sketch.sketchCurves.sketchLines
    n = len(cell)
    for i in range(n):
        x1, y1 = cell[i]
        x2, y2 = cell[(i + 1) % n]
        pt1 = adsk.core.Point3D.create(x1 * MM_TO_CM, y1 * MM_TO_CM, 0)
        pt2 = adsk.core.Point3D.create(x2 * MM_TO_CM, y2 * MM_TO_CM, 0)
        lines.addByTwoPoints(pt1, pt2)


def _draw_rounded_cell(sketch, cell, corner_radius):
    """Draw a cell with rounded corners (lines + arcs)."""
    segments = round_corners(cell, corner_radius)
    lines_coll = sketch.sketchCurves.sketchLines
    arcs_coll = sketch.sketchCurves.sketchArcs

    for seg in segments:
        if seg['type'] == 'line':
            pt1 = adsk.core.Point3D.create(
                seg['x1'] * MM_TO_CM, seg['y1'] * MM_TO_CM, 0)
            pt2 = adsk.core.Point3D.create(
                seg['x2'] * MM_TO_CM, seg['y2'] * MM_TO_CM, 0)
            lines_coll.addByTwoPoints(pt1, pt2)
        elif seg['type'] == 'arc':
            pt1 = adsk.core.Point3D.create(
                seg['x1'] * MM_TO_CM, seg['y1'] * MM_TO_CM, 0)
            mid = adsk.core.Point3D.create(
                seg['mx'] * MM_TO_CM, seg['my'] * MM_TO_CM, 0)
            pt2 = adsk.core.Point3D.create(
                seg['x2'] * MM_TO_CM, seg['y2'] * MM_TO_CM, 0)
            arcs_coll.addByThreePoints(pt1, mid, pt2)


def get_face_boundary(face):
    """Extract the outer boundary polygon from a BRepFace.

    Args:
        face: adsk.fusion.BRepFace

    Returns:
        List of (x, y) tuples in mm.
    """
    outer_loop = face.loops[0]
    boundary_points = []

    for edge in outer_loop.edges:
        evaluator = edge.evaluator
        _, start_param, end_param = evaluator.getParameterExtents()
        _, points = evaluator.getStrokes(start_param, end_param, 0.01)
        for pt in points:
            # Convert cm to mm
            boundary_points.append((pt.x / MM_TO_CM, pt.y / MM_TO_CM))

    # Remove duplicate consecutive points
    cleaned = [boundary_points[0]]
    for i in range(1, len(boundary_points)):
        px, py = boundary_points[i]
        lx, ly = cleaned[-1]
        if abs(px - lx) > 0.001 or abs(py - ly) > 0.001:
            cleaned.append((px, py))

    return cleaned


def get_exclude_circles(selections):
    """Extract exclusion circles from selected circular edges.

    Args:
        selections: List of selected entities (BRepEdge).

    Returns:
        List of (cx, cy, radius) tuples in mm.
    """
    circles = []
    for entity in selections:
        if hasattr(entity, 'geometry'):
            geom = entity.geometry
            if hasattr(geom, 'center') and hasattr(geom, 'radius'):
                cx = geom.center.x / MM_TO_CM  # cm to mm
                cy = geom.center.y / MM_TO_CM
                radius = geom.radius / MM_TO_CM
                circles.append((cx, cy, radius))
    return circles
