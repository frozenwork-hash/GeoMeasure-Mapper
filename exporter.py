import csv
import json
import os
from abc import ABC, abstractmethod

from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter, QPixmap

MAX_EXPORT_DIMENSION = 16_384
SCENE_PADDING = 10


class ExportError(Exception):
    """Data export error."""


def _require_scene(data: dict):
    scene = data.get("scene")
    if scene is None:
        raise ExportError("The 'scene' key is missing from data")
    return scene


def _scene_export_rect(scene) -> QRectF:
    rect = scene.sceneRect()
    if rect.isEmpty():
        rect = scene.sceneRect()
    if rect.isEmpty():
        raise ExportError("The scene is empty — nothing to export")

    rect.adjust(-SCENE_PADDING, -SCENE_PADDING, SCENE_PADDING, SCENE_PADDING)

    if rect.width() > MAX_EXPORT_DIMENSION or rect.height() > MAX_EXPORT_DIMENSION:
        raise ExportError(
            f"Scene size ({int(rect.width())}×{int(rect.height())}) "
            f"exceeds the {MAX_EXPORT_DIMENSION}px limit"
        )

    return rect


def _render_scene_to_painter(painter: QPainter, scene, rect: QRectF) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(
        painter,
        QRectF(0, 0, rect.width(), rect.height()),
        rect,
    )


class BaseExporter(ABC):
    """Abstract interface class for all future export formats."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable format name for the UI."""

    @property
    @abstractmethod
    def file_filter(self) -> str:
        """Filter for the QFileDialog (e.g. 'CSV File (*.csv)')."""

    @property
    @abstractmethod
    def default_ext(self) -> str:
        """Default file extension (e.g. '.csv')."""

    @abstractmethod
    def export(self, file_path: str, data: dict) -> None:
        """Main data-saving method."""


class PNGExporter(BaseExporter):
    """Export the graphics scene with the map and route to PNG."""

    @property
    def name(self) -> str:
        return "PNG Image"

    @property
    def file_filter(self) -> str:
        return "PNG Image (*.png)"

    @property
    def default_ext(self) -> str:
        return ".png"

    def export(self, file_path: str, data: dict) -> None:
        scene = _require_scene(data)
        rect = _scene_export_rect(scene)

        width = max(1, int(rect.width()))
        height = max(1, int(rect.height()))

        image = QPixmap(width, height)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        if not painter.isActive():
            raise ExportError(f"Failed to create the image for export")

        try:
            _render_scene_to_painter(painter, scene, rect)
        finally:
            painter.end()

        if not image.save(file_path):
            raise ExportError(f"Failed to save PNG: {file_path}")


class PDFExporter(BaseExporter):
    """Export the graphics scene with the map and route to PDF."""

    @property
    def name(self) -> str:
        return "PDF Document"

    @property
    def file_filter(self) -> str:
        return "PDF Document (*.pdf)"

    @property
    def default_ext(self) -> str:
        return ".pdf"

    def export(self, file_path: str, data: dict) -> None:
        scene = _require_scene(data)
        rect = _scene_export_rect(scene)

        writer = QPdfWriter(file_path)
        writer.setResolution(96)
        
        page_width = rect.width() * 0.75
        page_height = rect.height() * 0.75

        writer.setPageSize(
            QPageSize(QSizeF(page_width, page_height), QPageSize.Unit.Point)
        )
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point)

        painter = QPainter(writer)
        if not painter.isActive():
            raise ExportError(f"Failed to open the PDF for writing: {file_path}")

        try:
            _render_scene_to_painter(painter, scene, rect)
        finally:
            painter.end()


class CSVExporter(BaseExporter):
    """Export metadata and the segment table to CSV (Excel-compatible)."""

    @property
    def name(self) -> str:
        return "CSV Table"

    @property
    def file_filter(self) -> str:
        return "CSV File (*.csv)"

    @property
    def default_ext(self) -> str:
        return ".csv"

    def export(self, file_path: str, data: dict) -> None:
        unit = data.get("unit", "px")
        m_per_px = data.get("meters_per_pixel")
        segments = data.get("segments", [])
        total_dist = data.get("total_distance", 0.0)

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")

                writer.writerow(["=== MEASUREMENT METADATA ==="])
                writer.writerow(["Unit", unit])
                writer.writerow(
                    ["Scale (m/px)", f"{m_per_px:.6f}" if m_per_px else "Not set"]
                )
                writer.writerow(["Total length", f"{total_dist:.4f}", unit])
                writer.writerow([])

                writer.writerow(
                    [
                        "Segment #",
                        "X1 (px)",
                        "Y1 (px)",
                        "X2 (px)",
                        "Y2 (px)",
                        f"Length ({unit})",
                        "Length (px)",
                    ]
                )

                for seg in segments:
                    writer.writerow(
                        [
                            seg["index"],
                            f"{seg['p1_x']:.2f}",
                            f"{seg['p1_y']:.2f}",
                            f"{seg['p2_x']:.2f}",
                            f"{seg['p2_y']:.2f}",
                            f"{seg['dist_unit']:.4f}",
                            f"{seg['dist_px']:.2f}",
                        ]
                    )
        except OSError as exc:
            raise ExportError(f"Failed to save CSV: {file_path}") from exc


class JSONExporter(BaseExporter):
    """Export metadata and segments to JSON."""

    @property
    def name(self) -> str:
        return "JSON Data"

    @property
    def file_filter(self) -> str:
        return "JSON File (*.json)"

    @property
    def default_ext(self) -> str:
        return ".json"

    def export(self, file_path: str, data: dict) -> None:
        export_payload = {
            "unit": data.get("unit", "px"),
            "meters_per_pixel": data.get("meters_per_pixel"),
            "total_distance": data.get("total_distance", 0.0),
            "segments": data.get("segments", []),
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_payload, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise ExportError(f"Failed to save JSON: {file_path}") from exc


class ExportManager:
    """Manager that handles the list of available export formats."""

    def __init__(self):
        self._exporters: list[BaseExporter] = []

    def register(self, exporter: BaseExporter) -> None:
        """Register a new format/plugin."""
        self._exporters.append(exporter)

    def get_exporters(self) -> list[BaseExporter]:
        """List of registered exporters."""
        return list(self._exporters)

    def get_file_filters(self) -> str:
        """Builds the filter string for QFileDialog."""
        return ";;".join(e.file_filter for e in self._exporters)

    def _find_exporter(
        self, file_path: str, selected_filter: str
    ) -> BaseExporter | None:
        if selected_filter:
            for exporter in self._exporters:
                if exporter.file_filter == selected_filter:
                    return exporter

        for exporter in self._exporters:
            if os.path.splitext(file_path)[1].lower() == exporter.default_ext.lower():
                return exporter

        return None

    def export(self, file_path: str, selected_filter: str, data: dict) -> bool:
        """Finds the appropriate exporter and performs the write."""
        if not file_path:
            return False

        exporter = self._find_exporter(file_path, selected_filter)
        if exporter is None:
            return False

        if not file_path.lower().endswith(exporter.default_ext.lower()):
            file_path += exporter.default_ext

        exporter.export(file_path, data)
        return True


def create_default_export_manager() -> ExportManager:
    """Factory that creates a manager with all built-in formats."""
    manager = ExportManager()
    manager.register(PNGExporter())
    manager.register(PDFExporter())
    manager.register(CSVExporter())
    manager.register(JSONExporter())
    return manager
