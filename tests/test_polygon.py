"""Tests for polygon operations module."""

import math
import sys
import os

# Add parent directory to path so we can import lib modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'VoronoiPattern'))

from lib.polygon import (
    polygon_area,
    polygon_centroid,
    point_in_polygon,
    clip_polygon,
    offset_polygon,
    round_corners,
)


class TestPolygonArea:
    def test_unit_square_ccw(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert abs(polygon_area(square) - 100.0) < 1e-6

    def test_unit_square_cw(self):
        square = [(0, 0), (0, 10), (10, 10), (10, 0)]
        assert abs(polygon_area(square) + 100.0) < 1e-6

    def test_triangle(self):
        tri = [(0, 0), (10, 0), (5, 10)]
        assert abs(polygon_area(tri) - 50.0) < 1e-6

    def test_degenerate(self):
        assert polygon_area([]) == 0.0
        assert polygon_area([(0, 0)]) == 0.0
        assert polygon_area([(0, 0), (1, 1)]) == 0.0


class TestPolygonCentroid:
    def test_square(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        cx, cy = polygon_centroid(square)
        assert abs(cx - 5.0) < 1e-6
        assert abs(cy - 5.0) < 1e-6

    def test_triangle(self):
        tri = [(0, 0), (6, 0), (3, 6)]
        cx, cy = polygon_centroid(tri)
        assert abs(cx - 3.0) < 1e-6
        assert abs(cy - 2.0) < 1e-6


class TestPointInPolygon:
    def test_inside_square(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert point_in_polygon((5, 5), square) is True

    def test_outside_square(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert point_in_polygon((15, 5), square) is False
        assert point_in_polygon((-1, 5), square) is False

    def test_triangle(self):
        tri = [(0, 0), (10, 0), (5, 10)]
        assert point_in_polygon((5, 3), tri) is True
        assert point_in_polygon((0, 10), tri) is False


class TestClipPolygon:
    def test_polygon_fully_inside(self):
        poly = [(2, 2), (8, 2), (8, 8), (2, 8)]
        clip = (0, 0, 10, 10)
        result = clip_polygon(poly, clip)
        assert len(result) == 4

    def test_polygon_partially_outside(self):
        poly = [(-5, 2), (5, 2), (5, 8), (-5, 8)]
        clip = (0, 0, 10, 10)
        result = clip_polygon(poly, clip)
        assert len(result) == 4
        # All x values should be >= 0
        for x, y in result:
            assert x >= -1e-6
            assert y >= -1e-6

    def test_polygon_fully_outside(self):
        poly = [(20, 20), (30, 20), (30, 30), (20, 30)]
        clip = (0, 0, 10, 10)
        result = clip_polygon(poly, clip)
        assert len(result) == 0


class TestOffsetPolygon:
    def test_square_inset(self):
        square = [(0, 0), (20, 0), (20, 20), (0, 20)]
        result = offset_polygon(square, 2.0)
        assert result is not None
        assert len(result) == 4
        area = abs(polygon_area(result))
        expected = 16.0 * 16.0  # 256
        assert abs(area - expected) < 1.0

    def test_offset_too_large(self):
        square = [(0, 0), (4, 0), (4, 4), (0, 4)]
        result = offset_polygon(square, 3.0)
        assert result is None

    def test_triangle_inset(self):
        tri = [(0, 0), (20, 0), (10, 20)]
        result = offset_polygon(tri, 1.0)
        assert result is not None
        assert len(result) == 3
        # Area should be smaller than original
        assert abs(polygon_area(result)) < abs(polygon_area(tri))


class TestRoundCorners:
    def test_no_radius(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        segments = round_corners(square, 0)
        assert len(segments) == 4
        assert all(s['type'] == 'line' for s in segments)

    def test_with_radius(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        segments = round_corners(square, 1.0)
        lines = [s for s in segments if s['type'] == 'line']
        arcs = [s for s in segments if s['type'] == 'arc']
        assert len(arcs) == 4  # One arc per corner
        assert len(lines) == 4  # One line per edge

    def test_arc_has_midpoint(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        segments = round_corners(square, 1.0)
        for s in segments:
            if s['type'] == 'arc':
                assert 'mx' in s
                assert 'my' in s
