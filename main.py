import json
import threading
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QObject, Signal
from pynput import keyboard
from pynput.keyboard import GlobalHotKeys

from macro_runner import MacroRunner

CONFIG_FILE = "config.json"


# ---------- Qt-safe signal ----------
class KeySignal(QObject):
    captured = Signal(str)


# ---------- Row widget ----------
class MacroRow(QWidget):
    def __init__(self, entry, edit_callback):
        super().__init__()
        self.entry = entry
        self.edit_callback = edit_callback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)

        self.label = QLabel()
        self.edit_btn = QPushButton("✏️")
        self.edit_btn.setFixedWidth(34)

        self.edit_btn.clicked.connect(self.edit_callback)

        layout.addWidget(self.label)
        layout.addStretch()
        layout.addWidget(self.edit_btn)

        self.refresh()

    def refresh(self):
        repeat = self.entry.get("repeat", -1)
        rep_text = "Loop" if repeat < 0 else f"x{repeat}"
        self.label.setText(
            f'{self.entry["key"]} | {self.entry["delay"]} s | {rep_text}'
        )


# ---------- Main app ----------
class MacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")
        self.resize(520, 380)

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

        btns = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.start_btn = QPushButton("Start (F5)")
        self.stop_btn = QPushButton("Stop (F6)")

        btns.addWidget(self.add_btn)
        btns.addStretch()
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)

        layout.addWidget(self.list_widget)
        layout.addLayout(btns)

        # ---------- Connections ----------
        self.add_btn.clicked.connect(self.add_key)
        self.start_btn.clicked.connect(self.start_macro)
        self.stop_btn.clicked.connect(self.stop_macro)

        self.load_config()
        self.setup_hotkeys()

    # ---------- Hotkeys ----------
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
            self, "Repeat",
            "-1 = loop forever",
            -1, -1, 9999
        )
        if not ok:
            return

        entry = {"key": key, "delay": delay, "repeat": repeat}
        self.macros.append(entry)
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

    # ---------- UI refresh ----------
    def refresh_list(self):
        self.list_widget.clear()
        for entry in self.macros:
            item = QListWidgetItem()
            row = MacroRow(
                entry,
                lambda e=entry, r=None: self.edit_entry(e, r)
            )
            row.edit_callback = lambda e=entry, r=row: self.edit_entry(e, r)
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

