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
   git clone [https://github.com/frozenwork-hash/GeoMeasure-Mapper.git](https://github.com/frozenwork-hash/GeoMeasure-Mapper.git)
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

## Contributing
Issues and feature requests are welcome. Feel free to open an issue or submit a pull request.

## License
This project is licensed under the GPL-3.0 License.
