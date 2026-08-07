# GeoMeasure (Mapper)

A PyQt6 desktop application for cartographic measurements. Load your fantasy maps, world illustrations, or scanned documents — calibrate the scale, place points, and measure distances with precision.

## Features
- Load raster map images and multi-page PDF documents.
- Scale calibration — set the real-world distance using a reference segment on your map.
- Interactive measurements — place points, build routes, and get automatic distance calculations.
- Multiple measurement lines — create several lines with different colors; view per-segment distances, per-line totals, and grand total.
- Customizable coordinate grid — toggleable grid with pixel-based or metric-based step values.
- Adjustable DPI — fine-tune PDF import resolution (default 450 DPI) for optimal clarity.
- Compass overlay — interactive directional aid for orientation.
- Export your work — save measurement results and map views as PNG, PDF, CSV, or JSON.

## Building and Running from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/frozenwork-hash/GeoMeasure-Mapper.git
   cd GeoMeasure-Mapper

2. Install dependencies:
   ```bash
   pip install -r requirements.txt

3. Run the application:
   ```bash
   python main.py


## Executable for Windows
You can download the pre-compiled standalone executable (.exe) without needing a Python installation in the Releases section.

## Why This Project
Built by a writer, for writers, worldbuilders, and game masters. When you're designing a fantasy world, you need to know if your hero can travel from the Northern Keep to the Dragon's Peak in three days. This tool gives you that answer — without forcing you into complex GIS software.

## Usage Overview
- Load your map — use the import button to open an image or PDF.
- Calibrate the scale — mark two points on your map and enter the real distance they represent.
- Start measuring — click to place points and build measurement lines.
- View results — distances are displayed per segment and per line.
- Export — save your annotated map or export measurement data for further analysis.

## Session file format (.gms)

A `.gms` file is a **ZIP archive** containing:
- `data.json` – project data (points, lines, compasses, grid settings).
- `background.png` – the map image used as a background.

You can open it with any ZIP tool or rename to `.zip` to inspect/edit its contents.

### JSON structure (version 1.1)

```json
{
  "version": "1.1",
  "meters_per_pixel": 1419.3546,
  "points": [
    { "index": 1, "x": 2038.44, "y": 995.14 }
  ],
  "lines": [
    { "p1_index": 1, "p2_index": 2, "color": "#43ff43" }
  ],
  "compasses": [
    { "x": 3272.85, "y": 2787.38, "rotation": 0.0, "radius": 45, "ray_length": 2500 }
  ],
  "grid": {
    "show_grid": true,
    "grid_step_px": 70.45,
    "grid_value": 100.0,
    "grid_unit": "km"
  }
}
```

- `version` – data format version (1.1).

- `meters_per_pixel` – scale of the background image.

- `points` – array of measured points with pixel coordinates.

- `lines` – connections between points (by index) with a hex color.

- `compasses` – compass rose overlays: position, rotation (degrees), radius, ray length (pixels).

- `grid` – display settings for the measurement grid (unit can be any configured unit, e.g., km, m, custom).

Note: Colors are stored as #rrggbb hex strings. Coordinates are in pixels relative to the background image.

## V-1.2.0 Measurement
A modular vector measurement engine built for spatial analysis, area estimation, and path simplification in PyQt6.

* **Custom Area & Shape Tools**: Calculate polygonal surface areas using the Shoelace formula. Supports regular geometric shapes (circles, squares, $N$-sided polygons) and arbitrary user-defined boundaries.
* **3-Point Angle Finder**: Interactive vertex angle measurement with dynamic visual arcs and automatic acute/obtuse angle formatting.
* **Freehand Drawing with RDP Optimization**: Real-time freeform path sketching automatically simplified using the Ramer–Douglas–Peucker algorithm ($\epsilon = 2.0\text{ px}$) to compute exact total lengths.
* **Non-Modal Control Panel**: Floating tool selector dialog (`MeasurementDialog`) for switching active tools without interrupting viewport navigation.

## Contributing
Issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

## License
This project is licensed under the GPL-3.0 License.
