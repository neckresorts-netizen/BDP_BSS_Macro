import json
import threading
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox
)
from PySide6.QtCore import QObject, Signal
from pynput import keyboard
from pynput.keyboard import GlobalHotKeys

from macro_runner import MacroRunner
from settings_dialog import SettingsDialog

CONFIG_FILE = "config.json"


class KeySignal(QObject):
    captured = Signal(str)


class MacroRow(QWidget):
    def __init__(self, entry, edit_callback):
        super().__init__()
        self.entry = entry

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)

        self.label = QLabel()
        edit_btn = QPushButton("✏️")
        edit_btn.setFixedWidth(34)
        edit_btn.clicked.connect(edit_callback)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(edit_btn)

        self.refresh()

    def refresh(self):
        repeat = self.entry.get("repeat", -1)
        rep_text = "Loop" if repeat < 0 else f"x{repeat}"
        self.label.setText(
            f'{self.entry["key"]} | {self.entry["delay"]} s | {rep_text}'
        )


class MacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")
        self.resize(540, 400)

        # ---------- Styling ----------
        self.setStyleSheet("""
        QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
            font-size: 14px;
        }
        QPushButton {
            background-color: #3a3a3a;
            border-radius: 6px;
            padding: 8px;
        }
        QPushButton:hover {
            background-color: #505050;
        }
        QListWidget {
            background-color: #2a2a2a;
            border-radius: 6px;
        }
        """)

        # ---------- Data ----------
        self.macros = []
        self.start_key = "f5"
        self.stop_key = "f6"
        self.runner = MacroRunner()

        # ---------- Signals ----------
        self.key_signal = KeySignal()
        self.key_signal.captured.connect(self.on_key_captured)

        # ---------- UI ----------
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)

        buttons = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.settings_btn = QPushButton("Settings")
        self.start_btn = QPushButton()
        self.stop_btn = QPushButton()

        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.settings_btn)
        buttons.addStretch()
        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.stop_btn)

        layout.addWidget(self.list_widget)
        layout.addLayout(buttons)

        # ---------- Connections ----------
        self.add_btn.clicked.connect(self.add_key)
        self.settings_btn.clicked.connect(self.open_settings)
        self.start_btn.clicked.connect(self.start_macro)
        self.stop_btn.clicked.connect(self.stop_macro)

        self.load_config()
        self.update_button_labels()
        self.setup_hotkeys()

    # ---------- Settings ----------
    def open_settings(self):
        dialog = SettingsDialog(self.start_key, self.stop_key)
        if dialog.exec():
            self.start_key, self.stop_key = dialog.get_keys()
            self.update_button_labels()
            self.setup_hotkeys()
            self.save_config()

    def update_button_labels(self):
        self.start_btn.setText(f"Start ({self.start_key.upper()})")
        self.stop_btn.setText(f"Stop ({self.stop_key.upper()})")

    def setup_hotkeys(self):
        try:
            self.hotkeys.stop()
        except Exception:
            pass

        self.hotkeys = GlobalHotKeys({
            f"<{self.start_key}>": self.start_macro,
            f"<{self.stop_key}>": self.stop_macro
        })
        self.hotkeys.start()

    # ---------- Add key ----------
    def add_key(self):
        QMessageBox.information(self, "Add Key", "Press a key")

        def listen():
            def on_press(k):
                try:
                    key = k.char
                except AttributeError:
                    key = str(k).replace("Key.", "")
                self.key_signal.captured.emit(key)
                return False

            with keyboard.Listener(on_press=on_press) as l:
                l.join()

        threading.Thread(target=listen, daemon=True).start()

    def on_key_captured(self, key):
        delay, ok = QInputDialog.getDouble(
            self, "Delay", "Delay (seconds):", 0.5, 0.0, 60.0, 2
        )
        if not ok:
            return

        repeat, ok = QInputDialog.getInt(
            self, "Repeat (-1 = loop forever)",
            "-1 = loop forever",
            -1, -1, 9999
        )
        if not ok:
            return

        self.macros.append({
            "key": key,
            "delay": delay,
            "repeat": repeat
        })
        self.refresh_list()
        self.save_config()

    # ---------- Edit ----------
    def edit_entry(self, entry, row):
        delay, ok = QInputDialog.getDouble(
            self, "Edit Delay", "Seconds:", entry["delay"], 0.0, 60.0, 2
        )
        if not ok:
            return

        repeat, ok = QInputDialog.getInt(
            self, "Edit Repeat",
            "-1 = loop forever",
            entry.get("repeat", -1),
            -1, 9999
        )
        if not ok:
            return

        entry["delay"] = delay
        entry["repeat"] = repeat
        row.refresh()
        self.save_config()

    # ---------- Macro control ----------
    def start_macro(self):
        self.runner.start(self.macros)

    def stop_macro(self):
        self.runner.stop()

    # ---------- UI ----------
    def refresh_list(self):
        self.list_widget.clear()
        for entry in self.macros:
            item = QListWidgetItem()
            row = MacroRow(
                entry,
                lambda e=entry, r=None: self.edit_entry(e, r)
            )
            row_callback = lambda e=entry, r=row: self.edit_entry(e, r)
            row.layout().itemAt(2).widget().clicked.disconnect()
            row.layout().itemAt(2).widget().clicked.connect(row_callback)

            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    # ---------- Save / Load ----------
    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                self.macros = data.get("macros", [])
                self.start_key = data.get("start_key", "f5")
                self.stop_key = data.get("stop_key", "f6")
                self.refresh_list()
        except FileNotFoundError:
            pass

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "start_key": self.start_key,
                "stop_key": self.stop_key,
                "macros": self.macros
            }, f, indent=2)


if __name__ == "__main__":
    app = QApplication([])
    window = MacroApp()
    window.show()
    app.exec()

