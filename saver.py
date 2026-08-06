import json
import zipfile
import tempfile
import os
import shutil
from PyQt6.QtWidgets import QGraphicsPixmapItem
from PyQt6.QtCore import Qt

class SessionManager:
    """Handles saving and loading of the complete measurement session (.gms format)."""

    @staticmethod
    def save(view, output_path: str) -> bool:
        """
        Serializes points, lines, and the background image into a single ZIP archive.
        Returns True if successful, False otherwise.
        """
        # 1. Find the background pixmap in the scene
        pixmap_item = None
        for item in view.scene.items():
            if isinstance(item, QGraphicsPixmapItem):
                pixmap_item = item
                break
        
        if not pixmap_item or pixmap_item.pixmap().isNull():
            raise ValueError("No background image found on the scene.")

        # 2. Get the serialized data from the view
        session_data = view.to_dict()

        # 3. Use a temporary directory to prepare files before zipping
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = os.path.join(temp_dir, "session.json")
            img_path = os.path.join(temp_dir, "background.png")

            # Save JSON
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=4, ensure_ascii=False)

            # Save Pixmap as PNG
            pixmap_item.pixmap().save(img_path, "PNG")

            # 4. Pack into a ZIP archive (.gms)
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(json_path, arcname="session.json")
                zipf.write(img_path, arcname="background.png")
                
        return True

    @staticmethod
    def load(file_path: str, main_window) -> bool:
        """
        Unpacks a .gms archive, loads the background image, and restores the session data.
        Returns True if successful.
        """
        if not zipfile.is_zipfile(file_path):
            raise ValueError("The selected file is not a valid session archive.")

        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(file_path, 'r') as zipf:
                zipf.extractall(temp_dir)

            json_path = os.path.join(temp_dir, "session.json")
            img_path = os.path.join(temp_dir, "background.png")

            if not os.path.exists(json_path) or not os.path.exists(img_path):
                raise ValueError("Session archive is corrupted (missing JSON or background).")

            # 1. Read JSON data
            with open(json_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # 2. Load the image into the main window
            # We bypass load_image() slightly to directly load the extracted PNG
            from PyQt6.QtGui import QPixmap
            pixmap = QPixmap(img_path)
            
            main_window.clear_all()
            main_window.view.scene.addPixmap(pixmap)
            main_window.view.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            main_window.view.centerOn(pixmap.width() / 2, pixmap.height() / 2)

            # 3. Restore points and lines
            main_window.view.from_dict(session_data)
            
            # 4. Update the UI
            main_window.update_calculations()
            main_window.set_status("Session loaded successfully.")

        return True