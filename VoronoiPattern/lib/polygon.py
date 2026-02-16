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


def _seg_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    """Segment-segment intersection.

    Returns (t, ix, iy) where t is parameter along a->b, or None.
    """
    dabx, daby = bx - ax, by - ay
    dcdx, dcdy = dx - cx, dy - cy
    denom = dabx * dcdy - daby * dcdx
    if abs(denom) < 1e-12:
        return None
    t = ((cx - ax) * dcdy - (cy - ay) * dcdx) / denom
    s = ((cx - ax) * daby - (cy - ay) * dabx) / denom
    eps = 1e-10
    if -eps <= t <= 1 + eps and -eps <= s <= 1 + eps:
        t = max(0.0, min(1.0, t))
        return (t, ax + t * dabx, ay + t * daby)
    return None


def clip_polygon_to_boundary(polygon, boundary):
    """Clip polygon to an arbitrary (possibly concave) boundary polygon.

    Uses vertex classification and edge-boundary intersection rather
    than Sutherland-Hodgman, which fails for concave boundaries.

    Args:
        polygon: List of (x, y) tuples to clip.
        boundary: List of (x, y) tuples defining the clipping boundary.

    Returns:
        Clipped polygon as list of (x, y) tuples.
    """
    n_poly = len(polygon)
    n_bound = len(boundary)

    if n_poly < 3 or n_bound < 3:
        return []

    # Classify polygon vertices
    poly_inside = [point_in_polygon(p, boundary) for p in polygon]

    if all(poly_inside):
        return list(polygon)
    if not any(poly_inside):
        return []

    def find_all_ix(p1, p2):
        """All intersections of segment p1-p2 with boundary edges.
        Returns [(t, (ix,iy), bound_edge_idx)] sorted by t."""
        ixs = []
        x1, y1 = p1
        x2, y2 = p2
        for j in range(n_bound):
            bx1, by1 = boundary[j]
            bx2, by2 = boundary[(j + 1) % n_bound]
            r = _seg_intersect(x1, y1, x2, y2, bx1, by1, bx2, by2)
            if r:
                t, ix, iy = r
                ixs.append((t, (ix, iy), j))
        ixs.sort()
        # Remove near-duplicate intersections (adjacent boundary edges)
        cleaned = []
        for ix in ixs:
            if not cleaned or \
               (ix[1][0] - cleaned[-1][1][0]) ** 2 + \
               (ix[1][1] - cleaned[-1][1][1]) ** 2 > 1e-10:
                cleaned.append(ix)
        return cleaned

    def walk_boundary(exit_bedge, entry_bedge):
        """Walk boundary between exit and entry edges.
        Returns boundary vertices inside the polygon."""
        fwd_count = (entry_bedge - exit_bedge) % n_bound
        bwd_count = (exit_bedge - entry_bedge) % n_bound

        if fwd_count <= bwd_count:
            verts = []
            be = (exit_bedge + 1) % n_bound
            for _ in range(fwd_count):
                verts.append(boundary[be])
                be = (be + 1) % n_bound
        else:
            verts = []
            be = exit_bedge
            for _ in range(bwd_count):
                verts.append(boundary[be])
                be = (be - 1) % n_bound

        return [v for v in verts if point_in_polygon(v, polygon)]

    # Build result by walking polygon edges
    result = []
    last_exit_bedge = None

    for i in range(n_poly):
        j = (i + 1) % n_poly
        curr_in = poly_inside[i]
        next_in = poly_inside[j]
        ixs = find_all_ix(polygon[i], polygon[j])

        if curr_in:
            result.append(polygon[i])

        if curr_in and not next_in:
            # Exiting boundary
            if ixs:
                result.append(ixs[0][1])
                last_exit_bedge = ixs[0][2]

        elif not curr_in and next_in:
            # Entering boundary
            if ixs:
                entry_bedge = ixs[-1][2]
                if last_exit_bedge is not None:
                    result.extend(walk_boundary(last_exit_bedge, entry_bedge))
                    last_exit_bedge = None
                result.append(ixs[-1][1])

        elif not curr_in and not next_in and len(ixs) >= 2:
            # Edge passes through boundary (both endpoints outside)
            for k in range(0, len(ixs) - 1, 2):
                entry_bedge = ixs[k][2]
                if last_exit_bedge is not None:
                    result.extend(
                        walk_boundary(last_exit_bedge, entry_bedge))
                result.append(ixs[k][1])
                result.append(ixs[k + 1][1])
                last_exit_bedge = ixs[k + 1][2]

    # Remove near-duplicate points
    if len(result) < 3:
        return []
    cleaned = [result[0]]
    for p in result[1:]:
        if (p[0] - cleaned[-1][0]) ** 2 + \
           (p[1] - cleaned[-1][1]) ** 2 > 1e-12:
            cleaned.append(p)
    # Also check last vs first
    if len(cleaned) >= 2 and \
       (cleaned[-1][0] - cleaned[0][0]) ** 2 + \
       (cleaned[-1][1] - cleaned[0][1]) ** 2 < 1e-12:
        cleaned.pop()
    return cleaned if len(cleaned) >= 3 else []


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

    Scales the polygon toward its centroid so that the minimum
    distance from centroid to edges decreases by `distance`.
    This approach never produces self-intersections.

    Args:
        polygon: List of (x, y) tuples.
        distance: Offset distance (positive = inward).

    Returns:
        Offset polygon as list of (x, y) tuples, or None if
        the polygon collapses.
    """
    n = len(polygon)
    if n < 3:
        return None

    area = abs(polygon_area(polygon))
    if area < 1e-12:
        return None

    cx, cy = polygon_centroid(polygon)

    # Compute perimeter
    perimeter = 0.0
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        perimeter += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    if perimeter < 1e-12:
        return None

    # Approximate inradius: 2 * area / perimeter
    inradius = 2.0 * area / perimeter
    if inradius <= distance:
        return None

    scale = (inradius - distance) / inradius

    result = []
    for x, y in polygon:
        result.append((cx + (x - cx) * scale, cy + (y - cy) * scale))

    return result


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
