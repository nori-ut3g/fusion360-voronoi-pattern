"""Tests for Voronoi computation module."""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'VoronoiPattern'))

from lib.voronoi import circumcircle, bowyer_watson, compute_voronoi


class TestCircumcircle:
    def test_right_triangle(self):
        result = circumcircle((0, 0), (10, 0), (0, 10))
        assert result is not None
        cx, cy, r_sq = result
        assert abs(cx - 5.0) < 1e-6
        assert abs(cy - 5.0) < 1e-6
        assert abs(r_sq - 50.0) < 1e-6

    def test_equilateral(self):
        h = 10 * math.sqrt(3) / 2
        result = circumcircle((0, 0), (10, 0), (5, h))
        assert result is not None
        cx, cy, r_sq = result
        assert abs(cx - 5.0) < 1e-6

    def test_collinear(self):
        result = circumcircle((0, 0), (5, 0), (10, 0))
        assert result is None


class TestBowyerWatson:
    def test_three_points(self):
        points = [(0, 0), (10, 0), (5, 10)]
        triangles, all_points = bowyer_watson(points)
        # Should produce at least 1 triangle from original points
        assert len(triangles) > 0

    def test_four_points_square(self):
        points = [(0, 0), (10, 0), (10, 10), (0, 10)]
        triangles, all_points = bowyer_watson(points)
        # 4 points should produce 2 Delaunay triangles (plus super triangle related)
        assert len(triangles) >= 2

    def test_two_points(self):
        points = [(0, 0), (10, 0)]
        triangles, all_points = bowyer_watson(points)
        assert isinstance(triangles, list)


class TestComputeVoronoi:
    def test_basic(self):
        seeds = [(2, 2), (8, 2), (5, 8)]
        bbox = (0, 0, 10, 10)
        cells = compute_voronoi(seeds, bbox)
        assert len(cells) == 3
        # At least some cells should be non-None
        non_none = [c for c in cells if c is not None]
        assert len(non_none) >= 1

    def test_grid_seeds(self):
        seeds = []
        for x in range(2, 10, 3):
            for y in range(2, 10, 3):
                seeds.append((float(x), float(y)))
        bbox = (0, 0, 10, 10)
        cells = compute_voronoi(seeds, bbox)
        assert len(cells) == len(seeds)

    def test_single_point(self):
        cells = compute_voronoi([(5, 5)], (0, 0, 10, 10))
        assert len(cells) == 1

    def test_cells_have_vertices(self):
        seeds = [(3, 3), (7, 3), (5, 7), (3, 7), (7, 7)]
        bbox = (0, 0, 10, 10)
        cells = compute_voronoi(seeds, bbox)
        for cell in cells:
            if cell is not None:
                assert len(cell) >= 3  # Each cell should be a polygon

    def test_boundary_guard_seeds(self):
        """With boundary polygon, all cells should be generated."""
        seeds = [(3, 3), (7, 3), (5, 7), (3, 7), (7, 7)]
        bbox = (0, 0, 10, 10)
        boundary = [(0, 0), (10, 0), (10, 10), (0, 10)]
        cells = compute_voronoi(seeds, bbox, boundary=boundary)
        assert len(cells) == 5
        non_none = [c for c in cells if c is not None]
        assert len(non_none) == 5

    def test_corner_seeds_with_boundary(self):
        """Seeds near corners should produce valid cells with boundary."""
        # Place seeds near all 4 corners
        seeds = [(1, 1), (9, 1), (9, 9), (1, 9), (5, 5)]
        bbox = (0, 0, 10, 10)
        boundary = [(0, 0), (10, 0), (10, 10), (0, 10)]
        cells = compute_voronoi(seeds, bbox, boundary=boundary)
        assert len(cells) == 5
        # All cells should be valid (not None), especially corner ones
        for i, cell in enumerate(cells):
            assert cell is not None, f"Cell {i} is None"
            assert len(cell) >= 3, f"Cell {i} has < 3 vertices"

    def test_non_rectangular_boundary(self):
        """Non-rectangular boundary should still produce all cells."""
        # L-shaped boundary
        boundary = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
        seeds = [(2, 2), (7, 2), (2, 7), (3, 4)]
        bbox = (0, 0, 10, 10)
        cells = compute_voronoi(seeds, bbox, boundary=boundary)
        assert len(cells) == 4
        non_none = [c for c in cells if c is not None]
        assert len(non_none) == 4
