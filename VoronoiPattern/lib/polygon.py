"""
Pure Python polygon operations for Voronoi pattern generation.

No external dependencies (no numpy, scipy, shapely).
All coordinates are in mm.
"""

import math


def polygon_area(polygon):
    """Calculate polygon area using the Shoelace formula.

    Args:
        polygon: List of (x, y) tuples.

    Returns:
        Signed area (positive = CCW, negative = CW).
    """
    n = len(polygon)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def polygon_centroid(polygon):
    """Calculate polygon centroid.

    Args:
        polygon: List of (x, y) tuples.

    Returns:
        (cx, cy) tuple.
    """
    n = len(polygon)
    if n == 0:
        return (0.0, 0.0)
    if n <= 2:
        cx = sum(p[0] for p in polygon) / n
        cy = sum(p[1] for p in polygon) / n
        return (cx, cy)

    area = polygon_area(polygon)
    if abs(area) < 1e-12:
        cx = sum(p[0] for p in polygon) / n
        cy = sum(p[1] for p in polygon) / n
        return (cx, cy)

    cx = 0.0
    cy = 0.0
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    factor = 1.0 / (6.0 * area)
    return (cx * factor, cy * factor)


def point_in_polygon(point, polygon):
    """Test if a point is inside a polygon using ray casting.

    Args:
        point: (x, y) tuple.
        polygon: List of (x, y) tuples.

    Returns:
        True if point is inside the polygon.
    """
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def clip_polygon_by_edge(polygon, x1, y1, x2, y2):
    """Clip polygon by a single edge using Sutherland-Hodgman.

    The edge is defined by two points. Points on the left side
    (when looking from (x1,y1) to (x2,y2)) are kept.
    """
    if not polygon:
        return []

    def inside(px, py):
        return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1) >= 0

    def intersect(px1, py1, px2, py2):
        dx_edge = x2 - x1
        dy_edge = y2 - y1
        dx_seg = px2 - px1
        dy_seg = py2 - py1
        denom = dx_edge * dy_seg - dy_edge * dx_seg
        if abs(denom) < 1e-12:
            return (px2, py2)
        t = ((px1 - x1) * dy_seg - (py1 - y1) * dx_seg) / denom
        return (x1 + t * dx_edge, y1 + t * dy_edge)

    output = []
    n = len(polygon)
    for i in range(n):
        curr_x, curr_y = polygon[i]
        next_x, next_y = polygon[(i + 1) % n]
        curr_inside = inside(curr_x, curr_y)
        next_inside = inside(next_x, next_y)

        if curr_inside:
            output.append((curr_x, curr_y))
            if not next_inside:
                ix, iy = intersect(curr_x, curr_y, next_x, next_y)
                output.append((ix, iy))
        elif next_inside:
            ix, iy = intersect(curr_x, curr_y, next_x, next_y)
            output.append((ix, iy))

    return output


def clip_polygon(polygon, clip_rect):
    """Clip polygon to a rectangle using Sutherland-Hodgman algorithm.

    Args:
        polygon: List of (x, y) tuples.
        clip_rect: (min_x, min_y, max_x, max_y) tuple.

    Returns:
        Clipped polygon as list of (x, y) tuples.
    """
    min_x, min_y, max_x, max_y = clip_rect

    # Clip by each edge of the rectangle (CCW order)
    result = polygon
    # Bottom edge
    result = clip_polygon_by_edge(result, min_x, min_y, max_x, min_y)
    # Right edge
    result = clip_polygon_by_edge(result, max_x, min_y, max_x, max_y)
    # Top edge
    result = clip_polygon_by_edge(result, max_x, max_y, min_x, max_y)
    # Left edge
    result = clip_polygon_by_edge(result, min_x, max_y, min_x, min_y)

    return result


def offset_polygon(polygon, distance):
    """Offset (shrink) a polygon inward by the given distance.

    Each edge is shifted inward along its normal by `distance`.
    Adjacent shifted edges are intersected to form new vertices.

    Args:
        polygon: List of (x, y) tuples (CCW winding).
        distance: Offset distance (positive = inward).

    Returns:
        Offset polygon as list of (x, y) tuples, or None if
        the polygon collapses (self-intersects).
    """
    n = len(polygon)
    if n < 3:
        return None

    # Ensure CCW winding
    if polygon_area(polygon) < 0:
        polygon = list(reversed(polygon))

    # Compute inward-shifted edges
    shifted_edges = []
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-12:
            continue
        # Inward normal for CCW polygon: (-dy, dx) / length
        nx = -dy / length
        ny = dx / length
        shifted_edges.append((
            x1 + nx * distance, y1 + ny * distance,
            x2 + nx * distance, y2 + ny * distance,
        ))

    if len(shifted_edges) < 3:
        return None

    # Intersect adjacent shifted edges to find new vertices
    new_polygon = []
    m = len(shifted_edges)
    for i in range(m):
        ax1, ay1, ax2, ay2 = shifted_edges[i]
        bx1, by1, bx2, by2 = shifted_edges[(i + 1) % m]

        dax = ax2 - ax1
        day = ay2 - ay1
        dbx = bx2 - bx1
        dby = by2 - by1

        denom = dax * dby - day * dbx
        if abs(denom) < 1e-12:
            # Parallel edges — use midpoint of shared region
            new_polygon.append(((ax2 + bx1) / 2, (ay2 + by1) / 2))
            continue

        t = ((bx1 - ax1) * dby - (by1 - ay1) * dbx) / denom
        ix = ax1 + t * dax
        iy = ay1 + t * day
        new_polygon.append((ix, iy))

    # Check if the result is valid
    if len(new_polygon) < 3:
        return None

    result_area = polygon_area(new_polygon)
    if result_area <= 0:
        return None

    original_area = polygon_area(polygon)
    if result_area > original_area * 1.01:
        return None

    # Verify offset edges haven't crossed by checking that each new edge
    # direction is consistent with the corresponding original edge.
    # New edge i (from vertex i to i+1) lies on shifted_edge[(i+1)%m],
    # which should be parallel to original edge (i+1)%n.
    for i in range(m):
        orig_i = (i + 1) % n
        ox1, oy1 = polygon[orig_i]
        ox2, oy2 = polygon[(orig_i + 1) % n]
        odx, ody = ox2 - ox1, oy2 - oy1

        nx1, ny1 = new_polygon[i]
        nx2, ny2 = new_polygon[(i + 1) % m]
        ndx, ndy = nx2 - nx1, ny2 - ny1

        # Dot product should be positive (same direction)
        if odx * ndx + ody * ndy < 0:
            return None

    return new_polygon


def round_corners(polygon, radius):
    """Round polygon corners with circular arcs.

    Each vertex is replaced by an arc that is tangent to
    the two adjacent edges, offset by `radius`.

    Args:
        polygon: List of (x, y) tuples.
        radius: Fillet radius in mm.

    Returns:
        List of segment dicts. Each segment is either:
        - {'type': 'line', 'x1': ..., 'y1': ..., 'x2': ..., 'y2': ...}
        - {'type': 'arc', 'x1': ..., 'y1': ..., 'mx': ..., 'my': ...,
           'x2': ..., 'y2': ...}
          where (x1,y1) is arc start, (mx,my) is midpoint, (x2,y2) is end.
    """
    n = len(polygon)
    if n < 3 or radius <= 0:
        # Return as line segments
        segments = []
        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            segments.append({
                'type': 'line',
                'x1': x1, 'y1': y1,
                'x2': x2, 'y2': y2,
            })
        return segments

    # For each vertex, compute the tangent points and arc midpoint
    tangent_points = []  # (enter_x, enter_y, mid_x, mid_y, exit_x, exit_y)
    for i in range(n):
        prev_x, prev_y = polygon[(i - 1) % n]
        curr_x, curr_y = polygon[i]
        next_x, next_y = polygon[(i + 1) % n]

        # Vectors from current vertex to prev and next
        dx1 = prev_x - curr_x
        dy1 = prev_y - curr_y
        dx2 = next_x - curr_x
        dy2 = next_y - curr_y

        len1 = math.sqrt(dx1 * dx1 + dy1 * dy1)
        len2 = math.sqrt(dx2 * dx2 + dy2 * dy2)

        if len1 < 1e-12 or len2 < 1e-12:
            tangent_points.append(None)
            continue

        # Unit vectors
        ux1, uy1 = dx1 / len1, dy1 / len1
        ux2, uy2 = dx2 / len2, dy2 / len2

        # Half-angle between the two edges
        dot = ux1 * ux2 + uy1 * uy2
        dot = max(-1.0, min(1.0, dot))
        angle = math.acos(dot)

        if abs(angle) < 1e-6 or abs(angle - math.pi) < 1e-6:
            tangent_points.append(None)
            continue

        # Distance from vertex to tangent point along each edge
        tan_dist = radius / math.tan(angle / 2.0)

        # Clamp to half the edge length
        max_dist = min(len1, len2) * 0.4
        if tan_dist > max_dist:
            tan_dist = max_dist

        # Tangent points
        enter_x = curr_x + ux1 * tan_dist
        enter_y = curr_y + uy1 * tan_dist
        exit_x = curr_x + ux2 * tan_dist
        exit_y = curr_y + uy2 * tan_dist

        # Arc midpoint: along the angle bisector
        bisect_x = ux1 + ux2
        bisect_y = uy1 + uy2
        bisect_len = math.sqrt(bisect_x * bisect_x + bisect_y * bisect_y)
        if bisect_len < 1e-12:
            tangent_points.append(None)
            continue

        bisect_x /= bisect_len
        bisect_y /= bisect_len

        # Distance from vertex to arc center along bisector
        center_dist = radius / math.sin(angle / 2.0)
        center_x = curr_x + bisect_x * center_dist
        center_y = curr_y + bisect_y * center_dist

        # Arc midpoint is on the circle, along the bisector from center
        mid_x = center_x - bisect_x * radius
        mid_y = center_y - bisect_y * radius

        tangent_points.append((enter_x, enter_y, mid_x, mid_y, exit_x, exit_y))

    # Build segments
    segments = []
    for i in range(n):
        tp_curr = tangent_points[i]
        tp_next = tangent_points[(i + 1) % n]

        # Arc at current vertex
        if tp_curr is not None:
            enter_x, enter_y, mid_x, mid_y, exit_x, exit_y = tp_curr
            segments.append({
                'type': 'arc',
                'x1': enter_x, 'y1': enter_y,
                'mx': mid_x, 'my': mid_y,
                'x2': exit_x, 'y2': exit_y,
            })

        # Line from current vertex exit to next vertex enter
        if tp_curr is not None:
            lx1, ly1 = tp_curr[4], tp_curr[5]  # exit
        else:
            lx1, ly1 = polygon[i]

        if tp_next is not None:
            lx2, ly2 = tp_next[0], tp_next[1]  # enter
        else:
            lx2, ly2 = polygon[(i + 1) % n]

        dist = math.sqrt((lx2 - lx1) ** 2 + (ly2 - ly1) ** 2)
        if dist > 1e-6:
            segments.append({
                'type': 'line',
                'x1': lx1, 'y1': ly1,
                'x2': lx2, 'y2': ly2,
            })

    return segments
