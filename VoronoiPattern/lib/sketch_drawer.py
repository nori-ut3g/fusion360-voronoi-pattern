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

from .polygon import round_corners


def draw_voronoi_pattern(sketch, cells, corner_radius):
    """Draw Voronoi hole pattern on an existing sketch.

    Args:
        sketch: Fusion 360 Sketch object (already created on the target face).
        cells: List of Voronoi cell polygons (list of (x, y) tuples in cm).
        corner_radius: Corner rounding radius in cm (0 for sharp corners).
    """
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
        pt1 = adsk.core.Point3D.create(x1, y1, 0)
        pt2 = adsk.core.Point3D.create(x2, y2, 0)
        lines.addByTwoPoints(pt1, pt2)


def _draw_rounded_cell(sketch, cell, corner_radius):
    """Draw a cell with rounded corners (lines + arcs)."""
    segments = round_corners(cell, corner_radius)
    lines_coll = sketch.sketchCurves.sketchLines
    arcs_coll = sketch.sketchCurves.sketchArcs

    for seg in segments:
        if seg['type'] == 'line':
            pt1 = adsk.core.Point3D.create(seg['x1'], seg['y1'], 0)
            pt2 = adsk.core.Point3D.create(seg['x2'], seg['y2'], 0)
            lines_coll.addByTwoPoints(pt1, pt2)
        elif seg['type'] == 'arc':
            pt1 = adsk.core.Point3D.create(seg['x1'], seg['y1'], 0)
            mid = adsk.core.Point3D.create(seg['mx'], seg['my'], 0)
            pt2 = adsk.core.Point3D.create(seg['x2'], seg['y2'], 0)
            arcs_coll.addByThreePoints(pt1, mid, pt2)


def get_face_boundary(face, sketch):
    """Extract the outer boundary polygon from a BRepFace in sketch space.

    Args:
        face: adsk.fusion.BRepFace
        sketch: adsk.fusion.Sketch created on the face.

    Returns:
        List of (x, y) tuples in sketch-space cm.
    """
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
