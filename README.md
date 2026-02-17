# Fusion 360 Voronoi Pattern Generator

A Fusion 360 add-in that generates Voronoi lightening hole patterns on flat faces — designed for sheet metal parts and laser cutting.

![Voronoi Pattern Preview](docs/preview.png)
<!-- Replace with actual screenshot -->

## Features

- Generate Voronoi cell patterns on any planar face
- Adjustable parameters: seed count, rib width, edge margin, corner radius
- Automatic face hole detection (bolt holes, etc.) with configurable margin
- Mount hole exclusion zones (select circular edges to preserve)
- Density gradient option for stronger material near mount holes
- Reproducible patterns via random seed
- Pure Python — no external dependencies

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/nori-ut3g/fusion360-voronoi-pattern.git
   ```

2. Copy or symlink the `VoronoiPattern` folder to your Fusion 360 add-ins directory:

   **Windows:**
   ```
   %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\
   ```

   **macOS:**
   ```
   ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/
   ```

3. Open Fusion 360 → Tools → Add-Ins → enable **VoronoiPattern**

## Usage

1. Open a design with a flat face (e.g., a sheet metal part)
2. Go to **Tools** → **Voronoi Pattern**
3. Select a **planar face** to apply the pattern
4. (Optional) Select **circular edges** to exclude as mount holes
5. Adjust parameters:

   | Parameter | Default | Description |
   |---|---|---|
   | Seed Count | 40 | Number of Voronoi cells (10–200) |
   | Min Rib Width | 3.0 mm | Minimum material between holes |
   | Edge Margin | 5.0 mm | Margin from face edges |
   | Hole Margin | 2.0 mm | Margin around detected face holes |
   | Corner Radius | 1.0 mm | Fillet radius on hole corners (0 = sharp) |
   | Random Seed | 42 | For reproducible patterns |
   | Density Gradient | On | Denser cells near mount holes |

6. Click **OK** — a sketch with the Voronoi pattern is created
7. Use **Extrude → Cut** to create the holes

### Tips

- Faces with existing holes (bolt holes, etc.) are automatically detected. The pattern avoids these areas with the specified Hole Margin.
- Increase **Seed Count** for more, smaller cells. Decrease for fewer, larger cells.
- Set **Corner Radius** to 0 for sharp corners (useful for laser cutting).
- Use the same **Random Seed** to get reproducible patterns across runs.
- If some cells are missing near edges, try reducing **Edge Margin**.

## Algorithm

The pattern generation pipeline consists of 7 stages:

### 1. Boundary & Hole Extraction

The selected face's outer loop is extracted as a polygon in sketch-space coordinates using `modelToSketchSpace()`. Inner loops (holes from bolt holes, cutouts, etc.) are also extracted and expanded outward by the Hole Margin.

### 2. Seed Generation

Random seed points are placed inside the face boundary using rejection sampling:
- Points must be at least `edge_margin` from any boundary edge
- Points must be outside all exclusion zones (circular edges + expanded hole polygons)
- When **Density Gradient** is enabled, seed density increases near exclusion zones via distance-weighted acceptance probability

### 3. Voronoi Tessellation (Bowyer-Watson)

The Delaunay triangulation is computed using the Bowyer-Watson incremental algorithm, then converted to the dual Voronoi diagram:

1. **Delaunay Triangulation**: Each seed point is inserted incrementally. Triangles whose circumcircle contains the new point are removed, and the resulting polygonal hole is re-triangulated. Triangles are stored in a hash set for O(1) insertion and removal, keeping the algorithm efficient at high seed counts.
2. **Voronoi Dual**: The circumcenters of triangles adjacent to each seed form the Voronoi cell vertices, sorted by angle around the seed.

**Boundary guard seeds**: To ensure cells near the face boundary close properly, guard seeds are placed at regular intervals along the boundary perimeter, offset outward by the average cell spacing. This follows the actual face shape (not just the bounding box), ensuring correct cell closure at corners and along curved/non-rectangular boundaries.

### 4. Clipping

Each Voronoi cell passes through two clipping stages:
1. **Wide bounding box clip** — removes far-away vertices from infinite Voronoi regions
2. **Boundary clip** (Sutherland-Hodgman variant for arbitrary polygons) — clips to an inset boundary (`boundary - rib_width/2`) ensuring the edge margin

Both clipping stages use AABB (axis-aligned bounding box) pre-filtering on edge intersection tests, rejecting ~80% of candidate edge pairs before the full segment-intersection calculation. Boundary walks of 5 or fewer vertices skip the expensive point-in-polygon verification.

### 5. Cell Offset

Each clipped cell is offset inward by `rib_width / 2` using centroid scaling:
```
scale = (inradius - distance) / inradius
vertex' = centroid + (vertex - centroid) * scale
```
This creates the material ribs between cells. Cells that become too small (< 0.005 cm²) after offset are discarded.

### 6. Hole Exclusion

Cells are clipped against expanded hole polygons using `clip_polygon_outside`:
- If a hole is entirely inside a cell, a thin slit (bridge) converts the polygon-with-hole into a simple polygon, enabling Fusion 360 to recognize it as a closed profile.
- If a cell partially overlaps a hole, Sutherland-Hodgman clipping keeps the portion outside the hole.

### 7. Corner Rounding & Sketch Drawing

For each cell:
1. **Simplification**: Edges shorter than `corner_radius` (min 0.01 cm) are merged using a two-pass linear algorithm — pass 1 marks short-edge vertices for removal in a single forward scan, pass 2 handles the wrap-around edge between the last and first vertex. This O(n) approach replaces the previous iterative loop that could degrade to O(n²) with many short edges from boundary clipping.
2. **Corner rounding**: Each convex vertex is replaced by a circular arc tangent to both adjacent edges. The fillet radius is clamped to 40% of the shorter adjacent edge to prevent overlap. Very obtuse angles (>170°) are left sharp.
3. **Drawing**: Lines use `addByTwoPoints`, arcs use `addByThreePoints` with automatic fallback to lines if the arc creation fails. All operations are batched with `isComputeDeferred = True` for performance. A progress dialog with a Cancel button is shown during processing, updating every 5 cells via `adsk.doEvents()` to keep the UI responsive.

## Standalone Testing

The algorithm modules (`lib/`) have no Fusion 360 dependency and can be tested independently:

```bash
pip install pytest
pytest tests/ -v
```

## Project Structure

```
VoronoiPattern/           # Fusion 360 add-in folder
├── VoronoiPattern.py     # Add-in entry point & UI
├── VoronoiPattern.manifest
├── lib/
│   ├── voronoi.py        # Bowyer-Watson Delaunay → Voronoi
│   ├── polygon.py        # Clipping, offset, rounding, hole exclusion
│   ├── seed_generator.py # Seed point generation with exclusion zones
│   └── sketch_drawer.py  # Fusion sketch drawing with arc fallback
├── config/
│   └── defaults.json     # Default parameters
└── resources/            # Icons
tests/
├── test_voronoi.py       # Voronoi computation tests
├── test_polygon.py       # Polygon operations tests
├── test_seed_generator.py # Seed generation tests
└── visualize.py          # matplotlib preview
```

## Limitations

- Only planar faces are supported (curved surfaces are not yet supported)
- Seed count up to ~200 (beyond that, performance may degrade)
- The add-in creates sketch geometry only — extrude cut must be done manually

## License

[MIT](LICENSE)
