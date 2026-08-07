from PyQt6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QPushButton, QButtonGroup, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

class MeasurementDialog(QDialog):
    """
    Non-blocking dialog for selecting advanced measurement tools.
    Emits tool_changed signal with the name of the selected mode.
    """
    tool_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Measurement Tools")
        
        # Keep window on top but do not block the main application (modeless)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setModal(False)
        
        layout = QVBoxLayout(self)
        
        # UI Indicator for current mode
        self.lbl_indicator = QLabel("Current Mode: Idle")
        self.lbl_indicator.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(self.lbl_indicator)

        self.btn_group = QButtonGroup(self)

        # Radio buttons for tools
        self.rb_shapes = QRadioButton("Shapes (Circle / Square / Polygon)")
        self.rb_area = QRadioButton("Area (Select Line / Draw Polygon)")
        self.rb_angle = QRadioButton("Angle")
        self.rb_freehand = QRadioButton("Freehand Line")

        buttons = [self.rb_shapes, self.rb_area, self.rb_angle, self.rb_freehand]
        for idx, rb in enumerate(buttons, start=1):
            self.btn_group.addButton(rb, idx)
            layout.addWidget(rb)

        self.btn_group.idClicked.connect(self._on_selected)
        
        self.btn_exit = QPushButton("Exit Measurement Mode")
        self.btn_exit.clicked.connect(self._exit)
        layout.addWidget(self.btn_exit)

    def _on_selected(self, idx: int):
        modes = {1: "shapes", 2: "area", 3: "angle", 4: "freehand"}
        selected_mode = modes.get(idx, "idle")
        self.lbl_indicator.setText(f"Current Mode: {selected_mode.capitalize()}")
        self.tool_changed.emit(selected_mode)

    def _exit(self):
        self.btn_group.setExclusive(False)
        for b in self.btn_group.buttons():
            b.setChecked(False)
        self.btn_group.setExclusive(True)
        
        self.lbl_indicator.setText("Current Mode: Idle")
        self.tool_changed.emit("idle")

    def keyPressEvent(self, event):
        """Allows escaping the current tool by pressing Esc."""
        if event.key() == Qt.Key.Key_Escape:
            self._exit()
        else:
            super().keyPressEvent(event)