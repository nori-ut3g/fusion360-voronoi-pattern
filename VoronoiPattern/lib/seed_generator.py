"""
Seed point generation for Voronoi pattern.

Generates random seed points within a boundary polygon,
with optional density gradient near mount holes.

No external dependencies.
All coordinates are in mm.
"""

import math
import random

from .polygon import point_in_polygon


def generate_seeds(boundary, seed_count, edge_margin, exclude_circles=None,
                   exclude_polygons=None, density_gradient=True, random_seed=42):
    """Generate seed points within a boundary polygon.

    Args:
        boundary: List of (x, y) tuples defining the boundary polygon.
        seed_count: Target number of seed points.
        edge_margin: Margin from the boundary edges (mm).
        exclude_circles: List of (cx, cy, radius) tuples for mount holes
                         to exclude.
        exclude_polygons: List of polygons (list of (x, y) tuples) to
                          exclude (e.g. expanded hole regions).
        density_gradient: If True, increase density near mount holes.
        random_seed: Random seed for reproducibility.

    Returns:
        List of (x, y) seed points.
    """
    if exclude_circles is None:
        exclude_circles = []
    if exclude_polygons is None:
        exclude_polygons = []

    rng = random.Random(random_seed)

    # Compute bounding box of boundary
    min_x = min(p[0] for p in boundary)
    max_x = max(p[0] for p in boundary)
    min_y = min(p[1] for p in boundary)
    max_y = max(p[1] for p in boundary)

    if max_x - min_x < 1e-6 or max_y - min_y < 1e-6:
        return []

    seeds = []
    max_attempts = seed_count * 100

    for _ in range(max_attempts):
        if len(seeds) >= seed_count:
            break

        x = rng.uniform(min_x, max_x)
        y = rng.uniform(min_y, max_y)

        # Check if point is inside boundary polygon
        if not point_in_polygon((x, y), boundary):
            continue

        # Check if point is too close to boundary edges
        if not _is_margin_satisfied((x, y), boundary, edge_margin):
            continue

        # Check exclusion zones (mount holes)
        in_exclusion = False
        for cx, cy, r in exclude_circles:
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist < r:
                in_exclusion = True
                break
        if in_exclusion:
            continue

        # Check exclusion polygons (auto-detected hole regions)
        if exclude_polygons:
            in_poly_exclusion = False
            for hole_poly in exclude_polygons:
                if point_in_polygon((x, y), hole_poly):
                    in_poly_exclusion = True
                    break
            if in_poly_exclusion:
                continue

        # Density gradient: rejection sampling
        if density_gradient and exclude_circles:
            accept_prob = _density_probability((x, y), exclude_circles)
            if rng.random() > accept_prob:
                continue

        seeds.append((x, y))

    return seeds


def _is_margin_satisfied(point, polygon, margin):
    """Check if a point is at least `margin` away from all polygon edges."""
    px, py = point
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        dist = _point_to_segment_distance(px, py, x1, y1, x2, y2)
        if dist < margin:
            return False
    return True


def _point_to_segment_distance(px, py, x1, y1, x2, y2):
    """Compute the minimum distance from point (px,py) to segment (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-12:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)


def _density_probability(point, exclude_circles):
    """Compute acceptance probability for density gradient sampling.

    Points closer to mount holes have higher acceptance probability,
    resulting in smaller Voronoi cells (smaller holes, more material).
    Points far from mount holes have base acceptance probability.
    """
    px, py = point

    # Find minimum distance to any mount hole edge
    min_dist = float('inf')
    max_radius = 0.0
    for cx, cy, r in exclude_circles:
        dist = math.sqrt((px - cx) ** 2 + (py - cy) ** 2) - r
        min_dist = min(min_dist, dist)
        max_radius = max(max_radius, r)

    # Influence zone: within 3x the largest hole radius
    influence_range = max_radius * 3.0
    if influence_range < 1e-6:
        return 1.0

    if min_dist <= 0:
        return 1.0
    elif min_dist >= influence_range:
        return 0.5  # Base probability for distant points

    # Linear interpolation: closer = higher probability
    t = min_dist / influence_range
    return 1.0 - 0.5 * t  # 1.0 at hole edge, 0.5 at influence boundary
