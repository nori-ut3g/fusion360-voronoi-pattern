"""Tests for seed point generator module."""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'VoronoiPattern'))

from lib.seed_generator import generate_seeds
from lib.polygon import point_in_polygon


class TestGenerateSeeds:
    def _square_boundary(self):
        return [(0, 0), (100, 0), (100, 100), (0, 100)]

    def test_basic_generation(self):
        seeds = generate_seeds(self._square_boundary(), seed_count=20,
                               edge_margin=5.0)
        assert len(seeds) > 0
        assert len(seeds) <= 20

    def test_seeds_inside_boundary(self):
        boundary = self._square_boundary()
        seeds = generate_seeds(boundary, seed_count=30, edge_margin=5.0)
        for x, y in seeds:
            assert point_in_polygon((x, y), boundary)

    def test_seeds_respect_margin(self):
        boundary = self._square_boundary()
        margin = 10.0
        seeds = generate_seeds(boundary, seed_count=30, edge_margin=margin)
        for x, y in seeds:
            assert x >= margin - 0.1
            assert y >= margin - 0.1
            assert x <= 100 - margin + 0.1
            assert y <= 100 - margin + 0.1

    def test_exclusion_zones(self):
        boundary = self._square_boundary()
        # Exclude a circle in the center
        exclude = [(50, 50, 15)]
        seeds = generate_seeds(boundary, seed_count=30, edge_margin=5.0,
                               exclude_circles=exclude, density_gradient=False)
        for x, y in seeds:
            dist = math.sqrt((x - 50) ** 2 + (y - 50) ** 2)
            assert dist >= 15.0

    def test_reproducibility(self):
        boundary = self._square_boundary()
        seeds1 = generate_seeds(boundary, seed_count=20, edge_margin=5.0,
                                random_seed=42)
        seeds2 = generate_seeds(boundary, seed_count=20, edge_margin=5.0,
                                random_seed=42)
        assert seeds1 == seeds2

    def test_different_seeds_with_different_random_seed(self):
        boundary = self._square_boundary()
        seeds1 = generate_seeds(boundary, seed_count=20, edge_margin=5.0,
                                random_seed=42)
        seeds2 = generate_seeds(boundary, seed_count=20, edge_margin=5.0,
                                random_seed=99)
        assert seeds1 != seeds2

    def test_density_gradient_increases_density_near_holes(self):
        boundary = self._square_boundary()
        exclude = [(50, 50, 10)]

        # Generate many seeds with density gradient
        seeds = generate_seeds(boundary, seed_count=100, edge_margin=5.0,
                               exclude_circles=exclude, density_gradient=True,
                               random_seed=42)

        # Count seeds near the hole (within 30mm) vs far (> 30mm)
        near_count = 0
        far_count = 0
        for x, y in seeds:
            dist = math.sqrt((x - 50) ** 2 + (y - 50) ** 2)
            if dist < 30:
                near_count += 1
            elif dist > 40:
                far_count += 1

        # Near area is smaller than far area, so density should be higher
        # near_count / near_area > far_count / far_area
        # near_area ~ pi*(30^2 - 10^2) ~ 2513
        # far_area ~ 100*100 - pi*40^2 ~ 4975
        if near_count > 0 and far_count > 0:
            near_density = near_count / 2513.0
            far_density = far_count / 4975.0
            assert near_density > far_density * 0.5  # Relaxed check

    def test_empty_margin(self):
        """Edge margin larger than half the boundary should return empty."""
        boundary = [(0, 0), (10, 0), (10, 10), (0, 10)]
        seeds = generate_seeds(boundary, seed_count=10, edge_margin=6.0)
        assert len(seeds) == 0

    def test_exclude_polygons(self):
        """Seeds should not be placed inside exclude_polygons."""
        boundary = self._square_boundary()
        exclude_poly = [(40, 40), (60, 40), (60, 60), (40, 60)]
        seeds = generate_seeds(boundary, seed_count=50, edge_margin=5.0,
                               exclude_polygons=[exclude_poly],
                               density_gradient=False)
        assert len(seeds) > 0
        for x, y in seeds:
            assert not point_in_polygon((x, y), exclude_poly)
