"""Tests for sketch_drawer module (Fusion-independent parts)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'VoronoiPattern'))

from lib.sketch_drawer import _simplify_cell


class TestSimplifyCell:
    def test_no_short_edges(self):
        cell = [(0, 0), (10, 0), (10, 10), (0, 10)]
        result = _simplify_cell(cell, 1.0)
        assert len(result) == 4

    def test_all_short_edges_preserves_minimum(self):
        """When all edges are short, must keep at least 3 vertices."""
        cell = [(0, 0), (0.3, 0), (0.3, 0.3), (0, 0.3)]
        result = _simplify_cell(cell, 1.0)
        assert len(result) >= 3

    def test_one_short_edge(self):
        cell = [(0, 0), (10, 0), (10.01, 0.01), (10, 10), (0, 10)]
        result = _simplify_cell(cell, 0.1)
        assert len(result) == 4

    def test_triangle_unchanged(self):
        """Triangles (< 4 vertices) should be returned as-is."""
        cell = [(0, 0), (10, 0), (5, 10)]
        result = _simplify_cell(cell, 1.0)
        assert len(result) == 3

    def test_consecutive_short_edges(self):
        """Multiple consecutive short edges should be handled in one pass."""
        # 4 very close vertices + 1 far vertex
        cell = [(0, 0), (0.01, 0), (0.02, 0.01), (0.03, 0), (10, 5)]
        result = _simplify_cell(cell, 0.1)
        assert len(result) >= 3
        assert len(result) < 5  # some vertices should be removed

    def test_wrap_around_short_edge(self):
        """Short edge between last and first vertex should be handled."""
        cell = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0.01)]
        result = _simplify_cell(cell, 0.1)
        assert len(result) >= 3
        assert len(result) <= 4

    def test_large_polygon_performance(self):
        """Many short edges should complete quickly (O(n), not O(n^2))."""
        import time
        # 500 vertices with alternating short/long edges
        cell = []
        for i in range(250):
            cell.append((float(i), 0.0))
            cell.append((float(i) + 0.001, 0.5))
        start = time.time()
        result = _simplify_cell(cell, 0.01)
        elapsed = time.time() - start
        assert elapsed < 0.1  # should be nearly instant
        assert len(result) >= 3
