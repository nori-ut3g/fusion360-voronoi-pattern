"""
Development visualization tool for Voronoi pattern preview.

Usage:
    pip install matplotlib
    python tests/visualize.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'VoronoiPattern'))

from lib.voronoi import compute_voronoi
from lib.polygon import clip_polygon, offset_polygon, round_corners, polygon_area
from lib.seed_generator import generate_seeds


def visualize_pattern(boundary, seed_count=40, rib_width=3.0, edge_margin=5.0,
                      corner_radius=1.0, random_seed=42, exclude_circles=None,
                      density_gradient=True):
    """Generate and plot a Voronoi pattern."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.patches import Arc, FancyArrowPatch
        from matplotlib.path import Path as MplPath
    except ImportError:
        print("matplotlib is required: pip install matplotlib")
        return

    if exclude_circles is None:
        exclude_circles = []

    # Bounding box
    min_x = min(p[0] for p in boundary)
    max_x = max(p[0] for p in boundary)
    min_y = min(p[1] for p in boundary)
    max_y = max(p[1] for p in boundary)

    # Generate seeds
    seeds = generate_seeds(
        boundary, seed_count, edge_margin,
        exclude_circles=exclude_circles,
        density_gradient=density_gradient,
        random_seed=random_seed,
    )
    print(f"Generated {len(seeds)} seed points")

    # Compute Voronoi
    bbox = (min_x, min_y, max_x, max_y)
    cells = compute_voronoi(seeds, bbox)

    # Clip region (margin inset)
    clip_rect = (min_x + edge_margin, min_y + edge_margin,
                 max_x - edge_margin, max_y - edge_margin)

    # Process cells
    processed_cells = []
    for cell in cells:
        if cell is None:
            continue

        # Clip to margin rectangle
        clipped = clip_polygon(cell, clip_rect)
        if len(clipped) < 3:
            continue

        # Offset inward (half rib width for each cell)
        offset = offset_polygon(clipped, rib_width / 2.0)
        if offset is None:
            continue

        # Skip tiny cells
        if abs(polygon_area(offset)) < 1.0:
            continue

        processed_cells.append(offset)

    print(f"Processed {len(processed_cells)} cells")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))

    # Left plot: seeds and raw Voronoi
    ax1 = axes[0]
    ax1.set_title("Seeds & Raw Voronoi Cells")
    ax1.set_aspect('equal')

    # Draw boundary
    bx = [p[0] for p in boundary] + [boundary[0][0]]
    by = [p[1] for p in boundary] + [boundary[0][1]]
    ax1.plot(bx, by, 'b-', linewidth=2, label='Boundary')

    # Draw margin rectangle
    mx = [clip_rect[0], clip_rect[2], clip_rect[2], clip_rect[0], clip_rect[0]]
    my = [clip_rect[1], clip_rect[1], clip_rect[3], clip_rect[3], clip_rect[1]]
    ax1.plot(mx, my, 'b--', linewidth=1, alpha=0.5, label='Margin')

    # Draw seeds
    sx = [s[0] for s in seeds]
    sy = [s[1] for s in seeds]
    ax1.plot(sx, sy, 'r.', markersize=4)

    # Draw raw Voronoi cells
    for cell in cells:
        if cell is None:
            continue
        cx = [p[0] for p in cell] + [cell[0][0]]
        cy = [p[1] for p in cell] + [cell[0][1]]
        ax1.plot(cx, cy, 'g-', linewidth=0.5, alpha=0.5)

    # Draw exclusion circles
    for ex_cx, ex_cy, ex_r in exclude_circles:
        circle = plt.Circle((ex_cx, ex_cy), ex_r, fill=False,
                             color='red', linewidth=2, linestyle='--')
        ax1.add_patch(circle)

    ax1.legend(fontsize=8)

    # Right plot: final pattern (offset + rounded)
    ax2 = axes[1]
    ax2.set_title("Final Pattern (offset + rounded)")
    ax2.set_aspect('equal')

    # Draw boundary
    ax2.plot(bx, by, 'b-', linewidth=2)

    # Draw exclusion circles
    for ex_cx, ex_cy, ex_r in exclude_circles:
        circle = plt.Circle((ex_cx, ex_cy), ex_r, fill=True,
                             color='lightcoral', alpha=0.3)
        ax2.add_patch(circle)
        circle2 = plt.Circle((ex_cx, ex_cy), ex_r, fill=False,
                              color='red', linewidth=1.5)
        ax2.add_patch(circle2)

    # Draw processed cells
    for cell in processed_cells:
        if corner_radius > 0:
            segments = round_corners(cell, corner_radius)
            _draw_segments(ax2, segments, color='black', linewidth=1.2)
        else:
            cx = [p[0] for p in cell] + [cell[0][0]]
            cy = [p[1] for p in cell] + [cell[0][1]]
            ax2.fill(cx, cy, color='lightblue', alpha=0.3)
            ax2.plot(cx, cy, 'k-', linewidth=1.2)

    # Set limits
    pad = 5
    for ax in axes:
        ax.set_xlim(min_x - pad, max_x + pad)
        ax.set_ylim(min_y - pad, max_y + pad)

    plt.tight_layout()
    plt.savefig('voronoi_preview.png', dpi=150)
    print("Saved to voronoi_preview.png")
    plt.show()


def _draw_segments(ax, segments, color='black', linewidth=1.0):
    """Draw line and arc segments on a matplotlib axis."""
    for seg in segments:
        if seg['type'] == 'line':
            ax.plot([seg['x1'], seg['x2']], [seg['y1'], seg['y2']],
                    color=color, linewidth=linewidth)
        elif seg['type'] == 'arc':
            # Approximate arc with points
            x1, y1 = seg['x1'], seg['y1']
            mx, my = seg['mx'], seg['my']
            x2, y2 = seg['x2'], seg['y2']
            # Use quadratic bezier approximation through 3 points
            ts = [i / 20.0 for i in range(21)]
            xs = []
            ys = []
            for t in ts:
                # Quadratic bezier: P = (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
                b0 = (1 - t) ** 2
                b1 = 2 * (1 - t) * t
                b2 = t ** 2
                xs.append(b0 * x1 + b1 * mx + b2 * x2)
                ys.append(b0 * y1 + b1 * my + b2 * y2)
            ax.plot(xs, ys, color=color, linewidth=linewidth)


if __name__ == '__main__':
    # Example: rectangular plate with two mount holes
    boundary = [(0, 0), (120, 0), (120, 80), (0, 80)]
    exclude_circles = [
        (15, 15, 8),   # Bottom-left mount hole
        (105, 15, 8),  # Bottom-right mount hole
        (60, 65, 8),   # Top-center mount hole
    ]

    visualize_pattern(
        boundary,
        seed_count=60,
        rib_width=3.0,
        edge_margin=5.0,
        corner_radius=1.5,
        random_seed=42,
        exclude_circles=exclude_circles,
        density_gradient=True,
    )
