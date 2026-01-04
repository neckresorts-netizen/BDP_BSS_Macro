import json
import threading
import ctypes
import sys
from PySide6.QtWidgets import QLineEdit


from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox, QCheckBox
)
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QIcon, QPixmap

from pynput import keyboard
from pynput.keyboard import GlobalHotKeys

from macro_runner import MacroRunner
from settings_dialog import SettingsDialog


APP_ID = "MacroEditor.App"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
CONFIG_FILE = "config.json"


class KeySignal(QObject):
    captured = Signal(object)


class MacroRow(QWidget):
    def __init__(self, entry, edit_callback):
        super().__init__()
        self.entry = entry

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)

        self.enabled = QCheckBox()
        self.enabled.setChecked(entry.get("enabled", True))
        self.enabled.stateChanged.connect(self.toggle)

        self.key_lbl = QLabel(entry["key"])
        self.name_lbl = QLabel(entry["name"])
        self.timer_lbl = QLabel("—")
        self.timer_lbl.setStyleSheet("color:#9adfff; min-width:60px;")

        self.edit_btn = QPushButton("✏️")
        self.edit_btn.setFixedWidth(34)
        self.edit_btn.clicked.connect(lambda: edit_callback(entry))

        layout.addWidget(self.enabled)
        layout.addWidget(self.key_lbl)
        layout.addWidget(self.name_lbl, 1)
        layout.addWidget(self.timer_lbl)
        layout.addWidget(self.edit_btn)

    def toggle(self, state):
        self.entry["enabled"] = bool(state)

    def update_timer(self, seconds):
        self.timer_lbl.setText(f"{seconds:0.1f}s")

    def reset_timer(self):
        self.timer_lbl.setText("—")


class MacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(660, 470)

        self.setStyleSheet("""
        QWidget { background:#1e1e1e; color:white; font-size:14px; }
        QPushButton { background:#3a3a3a; border-radius:6px; padding:8px 14px; }
        QPushButton:hover { background:#505050; }
        QListWidget { background:#2a2a2a; border-radius:8px; }
        """)

        self.macros = []
        self.rows = {}

        self.start_key = "f5"
        self.stop_key = "f6"
        self.pause_key = "f7"

        self.runner = MacroRunner()
        self.runner.tick.connect(self.on_tick)
        self.runner.fired.connect(self.on_fired)
        self.runner.stopped.connect(self.on_stopped)

        self.key_signal = KeySignal()
        self.key_signal.captured.connect(self.on_key_captured)

        layout = QVBoxLayout(self)

        # HEADER
        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(QPixmap("icon.ico").scaled(26, 26, Qt.KeepAspectRatio))
        title = QLabel("BDP Macro")
        title.setStyleSheet("font-size:20px; font-weight:bold;")
        header.addStretch()
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # STATUS
        self.status = QLabel("Stopped")
        layout.addWidget(self.status)

        # LIST
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # BUTTONS
        btns = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.remove_btn = QPushButton("Remove")
        self.settings_btn = QPushButton("Settings")
        self.start_btn = QPushButton()
        self.pause_btn = QPushButton()
        self.stop_btn = QPushButton()

        btns.addWidget(self.add_btn)
        btns.addWidget(self.remove_btn)
        btns.addWidget(self.settings_btn)
        btns.addStretch()
        btns.addWidget(self.start_btn)
        btns.addWidget(self.pause_btn)
        btns.addWidget(self.stop_btn)
        layout.addLayout(btns)

        self.add_btn.clicked.connect(self.add_key)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.settings_btn.clicked.connect(self.open_settings)
        self.start_btn.clicked.connect(self.start_macro)
        self.pause_btn.clicked.connect(self.pause_macro)
        self.stop_btn.clicked.connect(self.stop_macro)

        self.load_config()
        self.update_buttons()
        self.setup_hotkeys()

    # ---------- TIMER SIGNALS ----------
    def on_tick(self, key, seconds):
        if key in self.rows:
            self.rows[key].update_timer(seconds)

    def on_fired(self, key):
        if key in self.rows:
            self.rows[key].reset_timer()

    def on_stopped(self):
        for row in self.rows.values():
            row.reset_timer()
        self.status.setText("Stopped")

    # ---------- LIST ----------
    def refresh_list(self):
        self.list_widget.clear()
        self.rows.clear()
        for m in self.macros:
            item = QListWidgetItem()
            row = MacroRow(m, self.edit_entry)
            self.rows[m["key"]] = row
            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    # ---------- CONTROLS ----------
    def start_macro(self):
        self.runner.start(self.macros)
        self.status.setText("Running")

    def pause_macro(self):
        if self.runner.paused:
            self.runner.resume()
            self.status.setText("Running")
        else:
            self.runner.pause()
            self.status.setText("Paused")

    def stop_macro(self):
        self.runner.stop()
        self.status.setText("Stopped")

    # ---------- ADD / EDIT ----------
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
        delay, ok = QInputDialog.getDouble(self, "Delay", "Seconds:", 0.5, 0, 1800, 2)
        if not ok:
            return

        repeat, ok = QInputDialog.getInt(self, "Repeat (-1 = loop)", "", -1, -1, 9999)
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

    def edit_entry(self, entry):
    name, ok = QInputDialog.getText(
        self,
        "Edit Name",
        "Name:",
        QLineEdit.Normal,
        entry["name"]
    )
    if not ok or not name:
        return

    delay, ok = QInputDialog.getDouble(
        self,
        "Edit Delay",
        "Seconds:",
        entry["delay"],
        0,
        1800,
        2
    )
    if not ok:
        return

    repeat, ok = QInputDialog.getInt(
        self,
        "Edit Repeat",
        "",
        entry["repeat"],
        -1,
        9999
    )
    if not ok:
        return

    entry.update(name=name, delay=delay, repeat=repeat)
    self.refresh_list()
    self.save_config()


    def remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.macros.pop(row)
            self.refresh_list()
            self.save_config()

    # ---------- SETTINGS ----------
    def open_settings(self):
        dlg = SettingsDialog(self.start_key, self.stop_key, self.pause_key)
        if dlg.exec():
            self.start_key, self.stop_key, self.pause_key = dlg.get_keys()
            self.update_buttons()
            self.setup_hotkeys()
            self.save_config()

    def update_buttons(self):
        self.start_btn.setText(f"Start ({self.start_key.upper()})")
        self.pause_btn.setText(f"Pause ({self.pause_key.upper()})")
        self.stop_btn.setText(f"Stop ({self.stop_key.upper()})")

    def setup_hotkeys(self):
        try:
            self.hotkeys.stop()
        except Exception:
            pass

        self.hotkeys = GlobalHotKeys({
            f"<{self.start_key}>": self.start_macro,
            f"<{self.pause_key}>": self.pause_macro,
            f"<{self.stop_key}>": self.stop_macro
        })
        self.hotkeys.start()

    # ---------- SAVE / LOAD ----------
    def load_config(self):
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                self.macros = data.get("macros", [])
                self.refresh_list()
        except FileNotFoundError:
            pass

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "start_key": self.start_key,
                "stop_key": self.stop_key,
                "pause_key": self.pause_key,
                "macros": self.macros
            }, f, indent=2)

    def closeEvent(self, event):
        self.runner.stop()
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico"))
    w = MacroApp()
    w.show()
    sys.exit(app.exec())
