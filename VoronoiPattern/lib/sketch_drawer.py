"""
Draw Voronoi pattern cells onto a Fusion 360 sketch.

All computation is done in sketch space (cm).
Boundary extraction converts model-space points to sketch-space
using sketch.modelToSketchSpace().
"""

import os

try:
    import adsk.core
    import adsk.fusion
except ImportError:
    # Allow import outside Fusion for testing
    adsk = None

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'debug.log')

def _log(msg):
    try:
        with open(_LOG_PATH, 'a') as f:
            f.write(msg + '\n')
    except Exception:
        pass

def _simplify_cell(cell, min_edge_len):
    """Remove vertices that create edges shorter than min_edge_len.

    When boundary clipping creates tiny edges, they split what should
    be a single corner into two vertices. Merging them back produces
    cleaner geometry for filleting.
    """
    import math
    result = list(cell)
    changed = True
    while changed and len(result) >= 3:
        changed = False
        new_result = []
        n = len(result)
        skip = set()
        for i in range(n):
            if i in skip:
                continue
            j = (i + 1) % n
            x1, y1 = result[i]
            x2, y2 = result[j]
            edge_len = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if edge_len < min_edge_len and len(result) - len(skip) > 3:
                # Keep the vertex with the sharper angle (more important corner)
                # For simplicity, keep vertex i and skip j
                new_result.append(result[i])
                skip.add(j)
                changed = True
            else:
                new_result.append(result[i])
        result = new_result
    return result


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
                cell = _simplify_cell(cell, corner_radius * 0.5)
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
    """
    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs

    for seg in segments:
        if seg['type'] == 'line':
            dx = seg['x2'] - seg['x1']
            dy = seg['y2'] - seg['y1']
            if dx * dx + dy * dy < 1e-10:
                continue
            pt1 = adsk.core.Point3D.create(seg['x1'], seg['y1'], 0)
            pt2 = adsk.core.Point3D.create(seg['x2'], seg['y2'], 0)
            lines.addByTwoPoints(pt1, pt2)
        elif seg['type'] == 'arc':
            x1, y1 = seg['x1'], seg['y1']
            mx, my = seg['mx'], seg['my']
            x2, y2 = seg['x2'], seg['y2']
            # Check for degenerate arc (collinear or coincident points)
            cross = (mx - x1) * (y2 - y1) - (my - y1) * (x2 - x1)
            d12 = (x2 - x1) ** 2 + (y2 - y1) ** 2
            if abs(cross) < 1e-8 or d12 < 1e-10:
                # Fall back to straight line
                if d12 >= 1e-10:
                    pt1 = adsk.core.Point3D.create(x1, y1, 0)
                    pt2 = adsk.core.Point3D.create(x2, y2, 0)
                    lines.addByTwoPoints(pt1, pt2)
                continue
            pt1 = adsk.core.Point3D.create(x1, y1, 0)
            mid = adsk.core.Point3D.create(mx, my, 0)
            pt2 = adsk.core.Point3D.create(x2, y2, 0)
            arcs.addByThreePoints(pt1, mid, pt2)


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
