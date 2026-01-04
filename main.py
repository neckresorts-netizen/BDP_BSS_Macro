# ---------------- Windows App ID (MUST be first) ----------------
import sys
import ctypes

if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "BigEyes101.MacroEditor"
    )

# ---------------- Imports ----------------
import json
import threading
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox, QCheckBox
)
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QIcon
from pynput import keyboard
from pynput.keyboard import GlobalHotKeys

from macro_runner import MacroRunner
from settings_dialog import SettingsDialog

CONFIG_FILE = "config.json"


# ---------------- Key Capture Signal ----------------
class KeySignal(QObject):
    captured = Signal(tuple)


# ---------------- Macro Row Widget ----------------
class MacroRow(QWidget):
    def __init__(self, entry, toggle_cb, edit_cb):
        super().__init__()
        self.entry = entry

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)

        self.enabled = QCheckBox()
        self.enabled.setChecked(entry.get("enabled", True))
        self.enabled.stateChanged.connect(toggle_cb)

        self.key_lbl = QLabel(entry["key"])
        self.name_lbl = QLabel(entry["name"])
        self.info_lbl = QLabel()

        self.edit_btn = QPushButton("✏️")
        self.edit_btn.setFixedWidth(34)
        self.edit_btn.clicked.connect(edit_cb)

        layout.addWidget(self.enabled)
        layout.addWidget(self.key_lbl)
        layout.addWidget(self.name_lbl, 1)
        layout.addWidget(self.info_lbl)
        layout.addWidget(self.edit_btn)

        self.refresh()

    def refresh(self):
        repeat = self.entry.get("repeat", -1)
        rep = "Loop" if repeat < 0 else f"x{repeat}"

        delay = self.entry["delay"]
        mins = int(delay // 60)
        secs = int(delay % 60)
        delay_txt = f"{mins}m {secs}s" if mins else f"{secs}s"

        self.key_lbl.setText(self.entry["key"])
        self.name_lbl.setText(self.entry["name"])
        self.info_lbl.setText(f"{delay_txt} | {rep}")


# ---------------- Main App ----------------
class MacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(640, 420)

        self.setStyleSheet("""
        QWidget { background:#1e1e1e; color:white; font-size:14px; }
        QPushButton { background:#3a3a3a; border-radius:6px; padding:8px; }
        QPushButton:hover { background:#505050; }
        QListWidget { background:#2a2a2a; border-radius:6px; }
        QCheckBox { padding-right: 6px; }
        """)

        self.macros = []
        self.start_key = "f5"
        self.stop_key = "f6"

        self.runner = MacroRunner()
        self.key_signal = KeySignal()
        self.key_signal.captured.connect(self.on_key_captured)

        # -------- Layout --------
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)

        btns = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.remove_btn = QPushButton("Remove")
        self.settings_btn = QPushButton("Settings")
        self.start_btn = QPushButton()
        self.stop_btn = QPushButton()

        btns.addWidget(self.add_btn)
        btns.addWidget(self.remove_btn)
        btns.addWidget(self.settings_btn)

        credits = QLabel("Credits to @big_eyes101")
        credits.setStyleSheet("color:#888888; font-size:12px;")
        credits.setAlignment(Qt.AlignCenter)
        btns.addWidget(credits)

        btns.addStretch()
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)

        layout.addWidget(self.list_widget)
        layout.addLayout(btns)

        # -------- Signals --------
        self.add_btn.clicked.connect(self.add_key)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.settings_btn.clicked.connect(self.open_settings)
        self.start_btn.clicked.connect(self.start_macro)
        self.stop_btn.clicked.connect(self.stop_macro)

        self.load_config()
        self.update_buttons()
        self.setup_hotkeys()

    # ---------------- Add Macro ----------------
    def add_key(self):
        name, ok = QInputDialog.getText(self, "Macro Name", "Name:")
        if not ok or not name:
            return

        QMessageBox.information(self, "Add Key", "Press a key")

        def listen():
            def on_press(k):
                try:
                    key = k.char
                except AttributeError:
                    key = str(k).replace("Key.", "")
                self.key_signal.captured.emit((name, key))
                return False

            with keyboard.Listener(on_press=on_press) as l:
                l.join()

        threading.Thread(target=listen, daemon=True).start()

    def on_key_captured(self, data):
        name, key = data

        delay, ok = QInputDialog.getDouble(
            self, "Delay", "Seconds (up to 30 minutes):",
            1.0, 0, 1800, 2
        )
        if not ok:
            return

        repeat, ok = QInputDialog.getInt(
            self, "Repeat (-1 = loop forever)", "", -1, -1, 9999
        )
        if not ok:
            return

        self.macros.append({
            "name": name,
            "key": key,
            "delay": delay,
            "repeat": repeat,
            "enabled": True
        })
        self.refresh_list()
        self.save_config()

    # ---------------- Edit ----------------
    def edit_entry(self, entry):
        name, ok = QInputDialog.getText(
            self, "Edit Name", "Name:", text=entry["name"]
        )
        if not ok:
            return

        delay, ok = QInputDialog.getDouble(
            self, "Edit Delay", "Seconds:",
            entry["delay"], 0, 1800, 2
        )
        if not ok:
            return

        repeat, ok = QInputDialog.getInt(
            self, "Edit Repeat", "", entry["repeat"], -1, 9999
        )
        if not ok:
            return

        entry.update(name=name, delay=delay, repeat=repeat)
        self.refresh_list()
        self.save_config()

    # ---------------- Remove ----------------
    def remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.macros.pop(row)
            self.refresh_list()
            self.save_config()

    # ---------------- Macro Control ----------------
    def start_macro(self):
        enabled = [m for m in self.macros if m.get("enabled", True)]
        self.runner.start(enabled)

    def stop_macro(self):
        self.runner.stop()

    # ---------------- UI ----------------
    def refresh_list(self):
        self.list_widget.clear()
        for entry in self.macros:
            item = QListWidgetItem()

            def toggle(state, e=entry):
                e["enabled"] = bool(state)
                self.save_config()

            row = MacroRow(
                entry,
                toggle_cb=toggle,
                edit_cb=lambda _, e=entry: self.edit_entry(e)
            )

            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    # ---------------- Settings ----------------
    def open_settings(self):
        dlg = SettingsDialog(self.start_key, self.stop_key)
        if dlg.exec():
            self.start_key, self.stop_key = dlg.get_keys()
            self.update_buttons()
            self.setup_hotkeys()
            self.save_config()

    def update_buttons(self):
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

    # ---------------- Save / Load ----------------
    def load_config(self):
        try:
            with open(CONFIG_FILE) as f:
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


# ---------------- Entry ----------------
if __name__ == "__main__":
    app = QApplication([])
    app.setApplicationName("Macro Editor")
    app.setOrganizationName("BigEyes101")
    app.setDesktopFileName("MacroEditor")  # last Windows hint
    app.setWindowIcon(QIcon("icon.ico"))

    w = MacroApp()
    w.show()
    app.exec()
