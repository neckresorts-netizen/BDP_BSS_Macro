from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QComboBox, QPushButton
)


class SettingsDialog(QDialog):
    def __init__(self, start_key, stop_key):
        super().__init__()
        self.setWindowTitle("Settings")
        self.setFixedSize(260, 160)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Start Macro Hotkey"))
        self.start_combo = QComboBox()
        self.start_combo.addItems([
            "f1","f2","f3","f4","f5","f6",
            "f7","f8","f9","f10","f11","f12"
        ])
        self.start_combo.setCurrentText(start_key)
        layout.addWidget(self.start_combo)

        layout.addWidget(QLabel("Stop Macro Hotkey"))
        self.stop_combo = QComboBox()
        self.stop_combo.addItems([
            "f1","f2","f3","f4","f5","f6",
            "f7","f8","f9","f10","f11","f12"
        ])
        self.stop_combo.setCurrentText(stop_key)
        layout.addWidget(self.stop_combo)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

    def get_keys(self):
        return (
            self.start_combo.currentText(),
            self.stop_combo.currentText()
        )
