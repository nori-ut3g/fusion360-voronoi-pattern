"""Performance tests for the Voronoi pipeline."""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'VoronoiPattern'))

from lib.voronoi import compute_voronoi
from lib.polygon import (
    clip_polygon, clip_polygon_to_boundary,
    offset_polygon, polygon_area,
)
from lib.seed_generator import generate_seeds


def test_200_seeds_completes_in_5_seconds():
    """Full pipeline with 200 seeds should complete within 5 seconds."""
    boundary = [(0, 0), (12, 0), (12, 8), (0, 8)]  # 120x80mm in cm
    seeds = generate_seeds(boundary, 200, 0.5, random_seed=42)
    assert len(seeds) > 100

    bbox = (0, 0, 12, 8)

    start = time.time()
    cells = compute_voronoi(seeds, bbox, boundary=boundary)

    inset = offset_polygon(boundary, 0.15)
    if inset is None:
        inset = boundary
    margin = 12
    wide_rect = (-margin, -margin, 12 + margin, 8 + margin)

    processed = []
    for cell in cells:
        if cell is None:
            continue
        clipped = clip_polygon(cell, wide_rect)
        if len(clipped) < 3:
            continue
        clipped = clip_polygon_to_boundary(clipped, inset)
        if len(clipped) < 3:
            continue
        o = offset_polygon(clipped, 0.15)
        if o and abs(polygon_area(o)) > 0.005:
            processed.append(o)

    elapsed = time.time() - start
    assert elapsed < 5.0, f"Pipeline took {elapsed:.1f}s (limit: 5s)"
    assert len(processed) > 50, f"Only {len(processed)} cells processed"


def test_100_seeds_completes_in_2_seconds():
    """Full pipeline with 100 seeds should complete within 2 seconds."""
    boundary = [(0, 0), (12, 0), (12, 8), (0, 8)]
    seeds = generate_seeds(boundary, 100, 0.5, random_seed=42)

    bbox = (0, 0, 12, 8)

    start = time.time()
    cells = compute_voronoi(seeds, bbox, boundary=boundary)

    inset = offset_polygon(boundary, 0.15)
    if inset is None:
        inset = boundary
    margin = 12
    wide_rect = (-margin, -margin, 12 + margin, 8 + margin)

    processed = []
    for cell in cells:
        if cell is None:
            continue
        clipped = clip_polygon(cell, wide_rect)
        if len(clipped) < 3:
            continue
        clipped = clip_polygon_to_boundary(clipped, inset)
        if len(clipped) < 3:
            continue
        o = offset_polygon(clipped, 0.15)
        if o and abs(polygon_area(o)) > 0.005:
            processed.append(o)

    elapsed = time.time() - start
    assert elapsed < 2.0, f"Pipeline took {elapsed:.1f}s (limit: 2s)"
    assert len(processed) > 30, f"Only {len(processed)} cells processed"
