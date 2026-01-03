import json
import threading
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QInputDialog, QMessageBox
)
from PySide6.QtCore import Signal, QObject
from pynput import keyboard

CONFIG_FILE = "config.json"


class KeySignal(QObject):
    key_captured = Signal(str)


class MacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")

        self.layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.add_button = QPushButton("Add Key")
        self.remove_button = QPushButton("Remove Selected")

        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.remove_button)

        self.add_button.clicked.connect(self.add_key)
        self.remove_button.clicked.connect(self.remove_key)

        self.key_signal = KeySignal()
        self.key_signal.key_captured.connect(self.on_key_captured)

        self.macros = []
        self.load_config()

    def add_key(self):
        QMessageBox.information(self, "Add Key", "Press a key to add")

        def listen():
            def on_press(key):
                try:
                    self.key_signal.key_captured.emit(key.char)
                except AttributeError:
                    self.key_signal.key_captured.emit(
                        str(key).replace("Key.", "")
                    )
                return False

            with keyboard.Listener(on_press=on_press) as listener:
                listener.join()

        threading.Thread(target=listen, daemon=True).start()

    def on_key_captured(self, key):
        delay, ok = QInputDialog.getInt(
            self, "Delay", "Delay (ms):", 100, 0
        )
        if not ok:
            return

        entry = {"key": key, "delay": delay}
        self.macros.append(entry)
        self.list_widget.addItem(f"{key} | {delay} ms")
        self.save_config()

    def remove_key(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            self.macros.pop(row)
            self.save_config()

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                self.macros = data.get("macros", [])
                for m in self.macros:
                    self.list_widget.addItem(
                        f"{m['key']} | {m['delay']} ms"
                    )
        except FileNotFoundError:
            pass

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "start_key": "f5",
                "stop_key": "f6",
                "macros": self.macros
            }, f, indent=2)


if __name__ == "__main__":
    app = QApplication([])
    window = MacroApp()
    window.show()
    app.exec()
