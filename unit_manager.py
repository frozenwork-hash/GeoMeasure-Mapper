import json
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt

# Defolt units
DEFAULT_UNITS = {
    "m": 1.0,
    "km": 1000.0,
    "miles (mi)": 1609.344,
    "nautical miles (nmi)": 1852.0,
    "feet (ft)": 0.3048,
    "cm": 0.01,
    "mm": 0.001,
    "µm": 1e-06,          # Micrometers
    "nm": 1e-09,          # Nanometers
    "pm": 1e-12,          # Picometers
    "angstroms (Å)": 1e-10 # Angstroms
}

CONFIG_FILE = "units_config.json"

class UnitManager:
    _units = None

    @classmethod
    def get_units(cls):
        if cls._units is None:
            cls.load()
        return cls._units

    @classmethod
    def load(cls):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cls._units = json.load(f)
            except Exception:
                cls._units = DEFAULT_UNITS.copy()
        else:
            cls._units = DEFAULT_UNITS.copy()

    @classmethod
    def save(cls, new_units):
        cls._units = new_units
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cls._units, f, indent=4, ensure_ascii=False)

    @classmethod
    def restore_defaults(cls):
        cls._units = DEFAULT_UNITS.copy()
        cls.save(cls._units)


class UnitSettingsDialog(QDialog):
    """UI dialog for configuring the list of units."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unit Configuration")
        self.resize(450, 400)

        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Unit Name", "Value (in meters)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.populate_table(UnitManager.get_units())

        # Buttons for controling the table
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("Add Unit")
        self.btn_add.clicked.connect(self.add_row)
        btn_layout.addWidget(self.btn_add)

        self.btn_remove = QPushButton("Remove Unit")
        self.btn_remove.clicked.connect(self.remove_row)
        btn_layout.addWidget(self.btn_remove)

        self.btn_reset = QPushButton("Restore Defaults")
        self.btn_reset.clicked.connect(self.reset_defaults)
        btn_layout.addWidget(self.btn_reset)

        layout.addLayout(btn_layout)

        # Save/Cancell buttons
        action_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_and_close)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        action_layout.addStretch()
        action_layout.addWidget(self.btn_save)
        action_layout.addWidget(self.btn_cancel)

        layout.addLayout(action_layout)

    def populate_table(self, units_dict):
        self.table.setRowCount(0)
        for name, val in units_dict.items():
            self.add_row(name, str(val))

    def add_row(self, name="", val=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(str(val)))

    def remove_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def reset_defaults(self):
        self.populate_table(DEFAULT_UNITS)

    def save_and_close(self):
        new_units = {}
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            val_item = self.table.item(row, 1)

            if not name_item or not val_item:
                continue

            name = name_item.text().strip()
            val_str = val_item.text().strip()

            if not name or not val_str:
                continue

            try:
                val_float = float(val_str)
                new_units[name] = val_float
            except ValueError:
                QMessageBox.warning(self, "Error", f"Invalid value for '{name}': {val_str}\nPlease enter a valid number (e.g. 1.0 or 1e-9).")
                return

        UnitManager.save(new_units)
        self.accept()