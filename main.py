import json
import threading
import ctypes
import sys

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox, QCheckBox, QLineEdit
)
from PySide6.QtCore import QObject, Signal, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap

from pynput import keyboard
from pynput.keyboard import GlobalHotKeys

from macro_runner import MacroRunner
from settings_dialog import SettingsDialog


# ---------- Windows App ID ----------
APP_ID = "MacroEditor.App"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

CONFIG_FILE = "config.json"


# ---------- Thread-safe key capture ----------
class KeySignal(QObject):
    captured = Signal(object)


# ---------- Row Widget ----------
class MacroRow(QWidget):
    def __init__(self, entry, edit_callback):
        super().__init__()
        self.entry = entry
        
        # Rounded background styling
        self.setStyleSheet("""
            MacroRow {
                background-color: #2d2d2d;
                border-radius: 10px;
                margin: 2px;
            }
            MacroRow:hover {
                background-color: #353535;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.enabled = QCheckBox()
        self.enabled.setChecked(entry.get("enabled", True))
        self.enabled.stateChanged.connect(self.toggle)
        self.enabled.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
                border: 2px solid #555;
                background-color: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
            QCheckBox::indicator:hover {
                border-color: #4a9eff;
            }
        """)

        self.key_lbl = QLabel(entry["key"].upper())
        self.key_lbl.setMinimumWidth(45)
        self.key_lbl.setAlignment(Qt.AlignCenter)
        self.key_lbl.setStyleSheet("""
            background-color: #4a9eff;
            color: white;
            font-weight: bold;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
        """)
        
        self.name_lbl = QLabel(entry["name"])
        self.name_lbl.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")

        # Info label showing delay and repeat
        repeat = entry.get("repeat", -1)
        rep = "Loop" if repeat < 0 else f"x{repeat}"
        self.info_lbl = QLabel(f'{entry["delay"]:.2f}s | {rep}')
        self.info_lbl.setStyleSheet("""
            color: #999;
            background-color: #252525;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
        """)
        self.info_lbl.setMinimumWidth(90)

        self.timer_lbl = QLabel("Ready")
        self.timer_lbl.setStyleSheet("""
            color: #9adfff;
            background-color: #1a3a4a;
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: bold;
            min-width: 70px;
            font-size: 12px;
        """)
        self.timer_lbl.setAlignment(Qt.AlignCenter)

        self.edit_btn = QPushButton("✏️")
        self.edit_btn.setFixedSize(42, 38)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border-radius: 8px;
                border: none;
                font-size: 18px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #4a9eff;
            }
            QPushButton:pressed {
                background-color: #3a7fd5;
            }
        """)
        self.edit_btn.clicked.connect(lambda: edit_callback(entry))

        layout.addWidget(self.enabled)
        layout.addWidget(self.key_lbl)
        layout.addWidget(self.name_lbl, 1)
        layout.addWidget(self.info_lbl)
        layout.addWidget(self.timer_lbl)
        layout.addWidget(self.edit_btn)

    def toggle(self, state):
        self.entry["enabled"] = bool(state)

    def update_timer(self, seconds):
        self.timer_lbl.setText(f"{seconds:0.1f}s")
        self.timer_lbl.setStyleSheet("""
            color: #ffaa00;
            background-color: #3a2a1a;
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: bold;
            min-width: 70px;
            font-size: 12px;
        """)

    def reset_timer(self):
        self.timer_lbl.setText("Ready")
        self.timer_lbl.setStyleSheet("""
            color: #9adfff;
            background-color: #1a3a4a;
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: bold;
            min-width: 70px;
            font-size: 12px;
        """)



# ---------- Main App ----------
class MacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(700, 470)

        self.setStyleSheet("""
        QWidget { background:#1e1e1e; color:white; font-size:14px; }
        QPushButton { background:#3a3a3a; border-radius:6px; padding:8px 14px; }
        QPushButton:hover { background:#505050; }
        QListWidget { 
            background:#2a2a2a; 
            border-radius:10px; 
            padding:8px;
            border: none;
        }
        QListWidget::item {
            background: transparent;
            border: none;
            padding: 3px;
        }
        QListWidget::item:selected {
            background: transparent;
            border: none;
        }
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

        # ---------- HEADER ----------
        header = QHBoxLayout()
        header.setSpacing(6)

        icon = QLabel()
        icon.setPixmap(QPixmap("icon.ico").scaled(26, 26, Qt.KeepAspectRatio))
        title = QLabel("BDP Macro")
        title.setStyleSheet("font-size:20px; font-weight:bold;")

        header.addStretch()
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # ---------- STATUS ----------
        self.status = QLabel("Stopped")
        self.status.setStyleSheet("font-weight:bold; padding:4px;")
        layout.addWidget(self.status)

        # ---------- LIST ----------
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # ---------- BUTTONS ----------
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

        # ---------- Signals ----------
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
            
            # Add some height for better spacing
            size_hint = row.sizeHint()
            item.setSizeHint(size_hint + QSize(0, 8))
            
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    # ---------- CONTROLS ----------
    def start_macro(self):
        self.runner.start([m for m in self.macros if m.get("enabled", True)])
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

    # ---------- ADD ----------
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
            self, "Delay", "Seconds:", 0.5, 0, 1800, 2
        )
        if not ok:
            return

        repeat, ok = QInputDialog.getInt(
            self, "Repeat (-1 = loop)", "", -1, -1, 9999
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

    # ---------- EDIT ----------
    def edit_entry(self, entry):
        name, ok = QInputDialog.getText(
            self, "Edit Name", "Name:", QLineEdit.Normal, entry["name"]
        )
        if not ok or not name:
            return

        delay, ok = QInputDialog.getDouble(
            self, "Edit Delay", "Seconds:",
            entry["delay"], 0, 1800, 2
        )
        if not ok:
            return

        repeat, ok = QInputDialog.getInt(
            self, "Edit Repeat", "",
            entry["repeat"], -1, 9999
        )
        if not ok:
            return

        entry["name"] = name
        entry["delay"] = delay
        entry["repeat"] = repeat
        
        self.refresh_list()
        self.save_config()

    # ---------- REMOVE ----------
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
                self.start_key = data.get("start_key", self.start_key)
                self.stop_key = data.get("stop_key", self.stop_key)
                self.pause_key = data.get("pause_key", self.pause_key)
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


# ---------- Run ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico"))
    w = MacroApp()
    w.show()
    sys.exit(app.exec())
