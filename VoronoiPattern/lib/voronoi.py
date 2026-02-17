"""
Bowyer-Watson Delaunay triangulation and Voronoi dual transform.

Pure Python implementation with no external dependencies.
All coordinates are in mm.
"""

import math
from collections import defaultdict


# Tolerance for floating point comparisons
EPS = 1e-9


def circumcircle(p1, p2, p3):
    """Compute the circumcircle of three points.

    Returns:
        (cx, cy, r_squared) or None if points are collinear.
    """
    ax, ay = p1
    bx, by = p2
    cx, cy = p3

    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < EPS:
        return None

    ux = ((ax * ax + ay * ay) * (by - cy) +
          (bx * bx + by * by) * (cy - ay) +
          (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) +
          (bx * bx + by * by) * (ax - cx) +
          (cx * cx + cy * cy) * (bx - ax)) / d

    r_sq = (ax - ux) ** 2 + (ay - uy) ** 2
    return (ux, uy, r_sq)


def _make_super_triangle(points):
    """Create a super triangle that contains all given points."""
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)

    dx = max_x - min_x
    dy = max_y - min_y
    d_max = max(dx, dy, 1.0)
    mid_x = (min_x + max_x) / 2.0
    mid_y = (min_y + max_y) / 2.0

    margin = d_max * 20.0
    p1 = (mid_x - margin, mid_y - margin)
    p2 = (mid_x + margin, mid_y - margin)
    p3 = (mid_x, mid_y + margin)
    return p1, p2, p3


def _edge_key(i, j):
    """Canonical edge key (smaller index first)."""
    return (min(i, j), max(i, j))


def bowyer_watson(points):
    """Perform Delaunay triangulation using the Bowyer-Watson algorithm.

    Args:
        points: List of (x, y) tuples.

    Returns:
        List of triangles, where each triangle is a tuple of three
        point indices into the input list. The super triangle vertices
        are at indices len(points), len(points)+1, len(points)+2.
    """
    n = len(points)
    if n < 2:
        return []

    sp1, sp2, sp3 = _make_super_triangle(points)
    all_points = list(points) + [sp1, sp2, sp3]

    # Use a set for O(1) triangle removal instead of O(n) list rebuild
    initial_tri = (n, n + 1, n + 2)
    triangles = {initial_tri}
    # Cache circumcircles: triangle tuple -> (cx, cy, r_sq)
    cc_cache = {}
    cc = circumcircle(sp1, sp2, sp3)
    if cc:
        cc_cache[initial_tri] = cc

    for idx in range(n):
        px, py = all_points[idx]

        # Find all triangles whose circumcircle contains the new point
        bad_triangles = []
        for tri in triangles:
            if tri not in cc_cache:
                p1 = all_points[tri[0]]
                p2 = all_points[tri[1]]
                p3 = all_points[tri[2]]
                cc_cache[tri] = circumcircle(p1, p2, p3)

            cc_val = cc_cache[tri]
            if cc_val is None:
                continue

            cx, cy, r_sq = cc_val
            dist_sq = (px - cx) ** 2 + (py - cy) ** 2
            if dist_sq < r_sq + EPS:
                bad_triangles.append(tri)

        # Find the boundary of the polygonal hole
        edge_count = defaultdict(int)
        for tri in bad_triangles:
            edges = [
                _edge_key(tri[0], tri[1]),
                _edge_key(tri[1], tri[2]),
                _edge_key(tri[2], tri[0]),
            ]
            for e in edges:
                edge_count[e] += 1

        boundary_edges = [e for e, count in edge_count.items() if count == 1]

        # Remove bad triangles using O(1) set discard
        for tri in bad_triangles:
            triangles.discard(tri)
            cc_cache.pop(tri, None)

        # Create new triangles from boundary edges to the new point
        for e in boundary_edges:
            verts = sorted((idx, e[0], e[1]))
            new_tri = (verts[0], verts[1], verts[2])
            triangles.add(new_tri)

            p1 = all_points[new_tri[0]]
            p2 = all_points[new_tri[1]]
            p3 = all_points[new_tri[2]]
            cc_val = circumcircle(p1, p2, p3)
            if cc_val:
                cc_cache[new_tri] = cc_val

    return list(triangles), all_points


def delaunay_to_voronoi(points, triangles, all_points):
    """Convert Delaunay triangulation to Voronoi diagram.

    Args:
        points: Original seed points (list of (x, y)).
        triangles: List of triangle tuples from bowyer_watson.
        all_points: All points including super triangle vertices.

    Returns:
        Dict mapping point index -> list of (x, y) Voronoi vertices
        (polygon, ordered CCW).
    """
    n = len(points)
    # Build mapping: point index -> list of triangles containing it
    point_to_triangles = defaultdict(list)
    for tri in triangles:
        for v in tri:
            point_to_triangles[v].append(tri)

    # For each triangle, compute circumcenter
    tri_circumcenters = {}
    for tri in triangles:
        p1 = all_points[tri[0]]
        p2 = all_points[tri[1]]
        p3 = all_points[tri[2]]
        cc = circumcircle(p1, p2, p3)
        if cc:
            tri_circumcenters[tri] = (cc[0], cc[1])

    # Build Voronoi cells for original points only
    voronoi_cells = {}
    for idx in range(n):
        tris = point_to_triangles[idx]

        # Collect circumcenters of adjacent triangles
        centers = []
        for tri in tris:
            if tri in tri_circumcenters:
                centers.append(tri_circumcenters[tri])

        if len(centers) < 3:
            continue

        # Sort circumcenters by angle around the seed point
        seed_x, seed_y = points[idx]
        centers.sort(key=lambda c: math.atan2(c[1] - seed_y, c[0] - seed_x))

        voronoi_cells[idx] = centers

    return voronoi_cells


def _boundary_guard_seeds(boundary, n_seeds):
    """Generate guard seeds outside the boundary for Voronoi cell closure.

    Places seeds at regular intervals along the boundary perimeter,
    offset outward. This ensures interior Voronoi cells close properly
    near the boundary, including corners and curved sections.
    """
    n = len(boundary)
    if n < 3:
        return []

    # Compute perimeter
    perimeter = 0.0
    for i in range(n):
        x1, y1 = boundary[i]
        x2, y2 = boundary[(i + 1) % n]
        perimeter += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    if perimeter < 1e-10:
        return []

    # Compute polygon area (shoelace) to determine winding direction
    area = 0.0
    for i in range(n):
        x1, y1 = boundary[i]
        x2, y2 = boundary[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    area /= 2.0

    # Outward normal sign: +1 for CCW, -1 for CW
    sign = 1.0 if area > 0 else -1.0

    # Offset distance: proportional to average seed spacing
    cell_area = abs(area) / max(n_seeds, 1)
    offset_dist = math.sqrt(cell_area)

    # Place guard seeds at regular intervals along the boundary
    interval = perimeter / max(n_seeds, 4)
    guards = []
    dist_remaining = 0.0

    for i in range(n):
        x1, y1 = boundary[i]
        x2, y2 = boundary[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        edge_len = math.sqrt(dx * dx + dy * dy)
        if edge_len < 1e-10:
            continue

        # Outward normal for this edge
        nx = sign * dy / edge_len
        ny = sign * (-dx) / edge_len

        # Walk along the edge, placing guards at interval spacing
        t = dist_remaining
        while t <= edge_len:
            frac = t / edge_len
            px = x1 + dx * frac
            py = y1 + dy * frac
            guards.append((px + nx * offset_dist, py + ny * offset_dist))
            t += interval

        dist_remaining = t - edge_len

    return guards


def compute_voronoi(seeds, boundary_bbox, boundary=None):
    """Compute Voronoi diagram with guard seeds for boundary handling.

    Args:
        seeds: List of (x, y) seed points.
        boundary_bbox: (min_x, min_y, max_x, max_y) bounding box.
        boundary: Optional boundary polygon (list of (x, y) tuples).
            When provided, guard seeds are placed along the actual
            boundary shape instead of using bbox mirror points.

    Returns:
        List of Voronoi cell polygons (list of (x, y) tuples),
        one per seed point. Some cells may be None if they couldn't
        be computed.
    """
    if len(seeds) < 2:
        return [None] * len(seeds)

    min_x, min_y, max_x, max_y = boundary_bbox

    if boundary is not None and len(boundary) >= 3:
        guard_seeds = _boundary_guard_seeds(boundary, len(seeds))
    else:
        # Fallback: mirror points across bbox edges
        guard_seeds = []
        for sx, sy in seeds:
            guard_seeds.append((2 * min_x - sx, sy))
            guard_seeds.append((2 * max_x - sx, sy))
            guard_seeds.append((sx, 2 * min_y - sy))
            guard_seeds.append((sx, 2 * max_y - sy))

    all_seeds = list(seeds) + guard_seeds
    n_original = len(seeds)

    triangles, all_points = bowyer_watson(all_seeds)
    voronoi_cells = delaunay_to_voronoi(all_seeds, triangles, all_points)

    # Extract cells for original seeds only
    result = []
    for i in range(n_original):
        cell = voronoi_cells.get(i)
        result.append(cell)

    return result
