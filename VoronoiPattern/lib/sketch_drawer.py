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
    for cell in cells:
        if len(cell) < 3:
            continue

        # Merge vertices that are too close, removing parasitic short edges
        cell = _simplify_cell(cell, corner_radius * 0.5)
        if len(cell) < 3:
            continue

        line_refs = _draw_straight_cell(sketch, cell)

        if corner_radius > 0 and line_refs:
            _fillet_cell(sketch, cell, line_refs, corner_radius)


def _draw_straight_cell(sketch, cell):
    """Draw a cell as a closed polyline (straight edges only).

    Returns:
        List of SketchLine references (or empty list outside Fusion).
    """
    lines = sketch.sketchCurves.sketchLines
    n = len(cell)
    line_refs = []
    for i in range(n):
        x1, y1 = cell[i]
        x2, y2 = cell[(i + 1) % n]
        pt1 = adsk.core.Point3D.create(x1, y1, 0)
        pt2 = adsk.core.Point3D.create(x2, y2, 0)
        line = lines.addByTwoPoints(pt1, pt2)
        line_refs.append(line)
    return line_refs


def _fillet_cell(sketch, cell, line_refs, corner_radius):
    """Apply fillets at each corner using Fusion 360 API."""
    import math
    arcs = sketch.sketchCurves.sketchArcs
    n = len(line_refs)

    # Compute edge lengths to clamp fillet radius
    edge_lengths = []
    for i in range(n):
        x1, y1 = cell[i]
        x2, y2 = cell[(i + 1) % n]
        edge_lengths.append(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))

    _log(f'  fillet_cell: n={n} corner_radius={corner_radius:.4f} edges={[f"{e:.4f}" for e in edge_lengths]}')

    for i in range(n):
        x1, y1 = cell[i]
        x2, y2 = cell[(i + 1) % n]
        x3, y3 = cell[(i + 2) % n]

        len_e1 = edge_lengths[i]
        len_e2 = edge_lengths[(i + 1) % n]
        min_adj = min(len_e1, len_e2)

        # Angle at vertex (i+1)
        dx1, dy1 = x1 - x2, y1 - y2
        dx2, dy2 = x3 - x2, y3 - y2
        if len_e1 < 1e-8 or len_e2 < 1e-8:
            _log(f'    v{i}: SKIP zero-length edge')
            continue
        dot = (dx1 * dx2 + dy1 * dy2) / (len_e1 * len_e2)
        angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot))))

        # Skip if nearly collinear (angle > 170°)
        if dot < -0.985:
            _log(f'    v{i}: SKIP collinear angle={angle_deg:.1f}')
            continue

        # Compute tangent length for this angle and clamp radius accordingly
        # tangent_length = radius / tan(angle/2)
        angle_rad = math.radians(angle_deg)
        half_tan = math.tan(angle_rad / 2.0)
        if half_tan < 1e-6:
            _log(f'    v{i}: SKIP degenerate angle={angle_deg:.1f}')
            continue

        # Max radius so tangent length stays under 70% of shortest adjacent edge
        max_radius = min_adj * 0.7 * half_tan
        radius = min(corner_radius, max_radius)
        if radius < 1e-4:
            _log(f'    v{i}: SKIP radius too small r={radius:.6f} angle={angle_deg:.1f} edges=({len_e1:.4f},{len_e2:.4f})')
            continue

        line1 = line_refs[i]
        line2 = line_refs[(i + 1) % n]
        # Pick points near the shared vertex (10% along each edge from vertex)
        # This ensures points stay on the line even after previous fillets trim edges
        t = 0.1
        pick1 = adsk.core.Point3D.create(
            x2 + (x1 - x2) * t, y2 + (y1 - y2) * t, 0)
        pick2 = adsk.core.Point3D.create(
            x2 + (x3 - x2) * t, y2 + (y3 - y2) * t, 0)
        try:
            arc = arcs.addFillet(line1, pick1, line2, pick2, radius)
            if arc:
                _log(f'    v{i}: OK radius={radius:.4f} angle={angle_deg:.1f} edges=({len_e1:.4f},{len_e2:.4f})')
            else:
                _log(f'    v{i}: NONE radius={radius:.4f} angle={angle_deg:.1f} edges=({len_e1:.4f},{len_e2:.4f})')
        except Exception as e:
            _log(f'    v{i}: FAIL radius={radius:.4f} angle={angle_deg:.1f} edges=({len_e1:.4f},{len_e2:.4f}) err={e}')


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
