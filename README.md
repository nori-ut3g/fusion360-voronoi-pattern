# Fusion 360 Voronoi Pattern Generator

A Fusion 360 add-in that generates Voronoi lightening hole patterns on flat faces — designed for sheet metal parts and laser cutting.

![Voronoi Pattern Preview](docs/preview.png)
<!-- Replace with actual screenshot -->

## Features

- Generate Voronoi cell patterns on any planar face
- Adjustable parameters: seed count, rib width, edge margin, corner radius
- Mount hole exclusion zones (select circular edges to preserve)
- Density gradient option for stronger material near mount holes
- Reproducible patterns via random seed
- Pure Python — no external dependencies

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/fusion360-voronoi-pattern.git
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
   | Corner Radius | 1.0 mm | Fillet radius on hole corners (0 = sharp) |
   | Random Seed | 42 | For reproducible patterns |
   | Density Gradient | On | Denser cells near mount holes |

6. Click **OK** — a sketch with the Voronoi pattern is created
7. Use **Extrude → Cut** to create the holes

## How It Works

1. **Seed Generation**: Random points are placed within the face boundary (respecting margins and exclusion zones)
2. **Delaunay Triangulation**: Bowyer-Watson algorithm triangulates the seed points
3. **Voronoi Dual**: Circumcenters of Delaunay triangles form Voronoi cell vertices
4. **Clipping & Offset**: Cells are clipped to the margin boundary and offset inward by half the rib width
5. **Corner Rounding**: Sharp corners are replaced with circular arcs
6. **Sketch Drawing**: The final pattern is drawn as sketch geometry on the selected face

Mirror points are added outside the boundary to ensure edge cells close properly.

## Standalone Testing

The algorithm modules (`lib/`) have no Fusion 360 dependency and can be tested independently:

```bash
pip install pytest matplotlib
cd tests
pytest -v
```

To preview patterns visually:

```bash
python tests/visualize.py
```

## Project Structure

```
VoronoiPattern/           # Fusion 360 add-in folder
├── VoronoiPattern.py     # Add-in entry point
├── VoronoiPattern.manifest
├── lib/
│   ├── voronoi.py        # Bowyer-Watson Delaunay → Voronoi
│   ├── polygon.py        # Clipping, offset, rounding
│   ├── seed_generator.py # Seed point generation
│   └── sketch_drawer.py  # Fusion sketch drawing
├── config/
│   └── defaults.json     # Default parameters
└── resources/            # Icons
tests/
├── test_voronoi.py
├── test_polygon.py
├── test_seed_generator.py
└── visualize.py          # matplotlib preview
```

## Limitations

- Only planar faces are supported (curved surfaces are not yet supported)
- Seed count up to ~200 (beyond that, performance may degrade)
- The add-in creates sketch geometry only — extrude cut must be done manually

## License

[MIT](LICENSE)
