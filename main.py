import json
import threading
import ctypes
import sys

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QInputDialog, QMessageBox, QCheckBox, QLineEdit,
    QDialog, QComboBox, QDoubleSpinBox
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


# ---------- Center Alignment Edit Dialog ----------
class CenterAlignmentDialog(QDialog):
    def __init__(self, center_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Center Alignment")
        self.setMinimumSize(400, 350)
        
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #ffffff; }
            QLabel { color: #dddddd; padding: 2px; }
            QComboBox, QDoubleSpinBox {
                background-color: #2a2a2a;
                color: #ffffff;
                padding: 8px;
                border-radius: 6px;
                border: 1px solid #3a3a3a;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover { background-color: #505050; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Center Alignment Macro")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        desc = QLabel("Presses: Left (,) → 1ms → Right (.) or Right (.) → 1ms → Left (,)")
        desc.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(desc)
        
        # Mode selection
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Auto", "Manual"])
        self.mode_combo.setCurrentText(center_config.get("mode", "Auto"))
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        layout.addWidget(self.mode_combo)
        
        # Manual keybinds
        self.manual_label = QLabel("Trigger Keys:")
        self.manual_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.manual_label)
        
        manual_layout = QHBoxLayout()
        
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Left Right"))
        self.key1_btn = QPushButton(center_config.get("trigger_key1", "f").upper())
        self.key1_btn.clicked.connect(lambda: self.capture_key(1))
        left_layout.addWidget(self.key1_btn)
        
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Right Left"))
        self.key2_btn = QPushButton(center_config.get("trigger_key2", "g").upper())
        self.key2_btn.clicked.connect(lambda: self.capture_key(2))
        right_layout.addWidget(self.key2_btn)
        
        manual_layout.addLayout(left_layout)
        manual_layout.addLayout(right_layout)
        
        self.manual_widget = QWidget()
        self.manual_widget.setLayout(manual_layout)
        layout.addWidget(self.manual_widget)
        
        # Auto settings
        self.auto_label = QLabel("Auto Settings:")
        self.auto_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.auto_label)
        
        auto_layout = QVBoxLayout()
        
        pattern_label = QLabel("Pattern:")
        auto_layout.addWidget(pattern_label)
        
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(["Alternate Both", "Only Left Right", "Only Right Left"])
        self.pattern_combo.setCurrentText(center_config.get("pattern", "Alternate Both"))
        auto_layout.addWidget(self.pattern_combo)
        
        interval_label = QLabel("Interval (seconds):")
        auto_layout.addWidget(interval_label)
        
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 1800)
        self.interval_spin.setDecimals(2)
        self.interval_spin.setValue(center_config.get("interval", 1.0))
        auto_layout.addWidget(self.interval_spin)
        
        self.auto_widget = QWidget()
        self.auto_widget.setLayout(auto_layout)
        layout.addWidget(self.auto_widget)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
        self.on_mode_changed(self.mode_combo.currentText())
        
        self.key_signal = KeySignal()
        self.key_signal.captured.connect(self.on_key_captured)
        self.capturing_key = None
    
    def on_mode_changed(self, mode):
        is_manual = mode == "Manual"
        self.manual_label.setVisible(is_manual)
        self.manual_widget.setVisible(is_manual)
        self.auto_label.setVisible(not is_manual)
        self.auto_widget.setVisible(not is_manual)
    
    def capture_key(self, key_num):
        self.capturing_key = key_num
        QMessageBox.information(self, "Capture Key", "Press a key")
        
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
        if self.capturing_key == 1:
            self.key1_btn.setText(key.upper())
        elif self.capturing_key == 2:
            self.key2_btn.setText(key.upper())
        self.capturing_key = None
    
    def get_config(self):
        return {
            "mode": self.mode_combo.currentText(),
            "trigger_key1": self.key1_btn.text().lower(),
            "trigger_key2": self.key2_btn.text().lower(),
            "pattern": self.pattern_combo.currentText(),
            "interval": self.interval_spin.value()
        }


# ---------- Row Widget ----------
class MacroRow(QWidget):
    def __init__(self, entry, edit_callback, is_center=False):
        super().__init__()
        self.entry = entry
        self.is_center = is_center
        
        # Rounded background styling
        bg_color = "#2d3d2d" if is_center else "#2d2d2d"
        self.setStyleSheet(f"""
            MacroRow {{
                background-color: {bg_color};
                border-radius: 10px;
                margin: 2px;
            }}
            MacroRow:hover {{
                background-color: {"#354535" if is_center else "#353535"};
            }}
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

        if is_center:
            self.key_lbl = QLabel("⚙️")
            self.key_lbl.setMinimumWidth(45)
            self.key_lbl.setAlignment(Qt.AlignCenter)
            self.key_lbl.setStyleSheet("""
                background-color: #5a9e5a;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 16px;
            """)
        else:
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

        # Info label
        if is_center:
            mode = entry.get("center_config", {}).get("mode", "Auto")
            if mode == "Auto":
                pattern = entry.get("center_config", {}).get("pattern", "Alternate Both")
                interval = entry.get("center_config", {}).get("interval", 1.0)
                if pattern == "Alternate Both":
                    info_text = f"Auto | Alt | {interval:.2f}s"
                elif pattern == "Only Left Right":
                    info_text = f"Auto | L-R | {interval:.2f}s"
                else:
                    info_text = f"Auto | R-L | {interval:.2f}s"
            else:
                key1 = entry.get("center_config", {}).get("trigger_key1", "f")
                key2 = entry.get("center_config", {}).get("trigger_key2", "g")
                info_text = f"Manual | {key1.upper()}/{key2.upper()}"
            self.info_lbl = QLabel(info_text)
        else:
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
        self.info_lbl.setMinimumWidth(120)

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
    
    def refresh_info(self):
        if self.is_center:
            mode = self.entry.get("center_config", {}).get("mode", "Auto")
            if mode == "Auto":
                pattern = self.entry.get("center_config", {}).get("pattern", "Alternate Both")
                interval = self.entry.get("center_config", {}).get("interval", 1.0)
                if pattern == "Alternate Both":
                    info_text = f"Auto | Alt | {interval:.2f}s"
                elif pattern == "Only Left Right":
                    info_text = f"Auto | L-R | {interval:.2f}s"
                else:
                    info_text = f"Auto | R-L | {interval:.2f}s"
            else:
                key1 = self.entry.get("center_config", {}).get("trigger_key1", "f")
                key2 = self.entry.get("center_config", {}).get("trigger_key2", "g")
                info_text = f"Manual | {key1.upper()}/{key2.upper()}"
            self.info_lbl.setText(info_text)


# ---------- Main App ----------
class MacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Editor")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(750, 470)

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
        self.center_alignment = {
            "name": "Center Alignment",
            "enabled": True,
            "is_center": True,
            "center_config": {
                "mode": "Auto",
                "trigger_key1": "f",
                "trigger_key2": "g",
                "pattern": "Alternate Both",
                "interval": 1.0
            }
        }
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
        
        self.manual_trigger_listener = None

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
        
        self.credits = QLabel("Created by Big_eyes101")
        self.credits.setStyleSheet("color: #888888; font-size: 12px;")
        self.credits.setAlignment(Qt.AlignCenter)
        
        self.start_btn = QPushButton()
        self.pause_btn = QPushButton()
        self.stop_btn = QPushButton()

        btns.addWidget(self.add_btn)
        btns.addWidget(self.remove_btn)
        btns.addWidget(self.settings_btn)
        btns.addStretch()
        btns.addWidget(self.credits)
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
        self.stop_manual_trigger()

    # ---------- LIST ----------
    def refresh_list(self):
        self.list_widget.clear()
        self.rows.clear()

        # Add center alignment first
        item = QListWidgetItem()
        row = MacroRow(self.center_alignment, self.edit_center_alignment, is_center=True)
        self.rows["_center_"] = row
        size_hint = row.sizeHint()
        item.setSizeHint(size_hint + QSize(0, 8))
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row)

        # Add regular macros
        for m in self.macros:
            item = QListWidgetItem()
            row = MacroRow(m, self.edit_entry)
            self.rows[m["key"]] = row
            size_hint = row.sizeHint()
            item.setSizeHint(size_hint + QSize(0, 8))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    # ---------- CONTROLS ----------
    def start_macro(self):
        regular_macros = [m for m in self.macros if m.get("enabled", True)]
        
        # Handle center alignment
        if self.center_alignment.get("enabled", True):
            mode = self.center_alignment["center_config"]["mode"]
            if mode == "Auto":
                # Add as regular macro with special handling
                self.runner.start_with_center(regular_macros, self.center_alignment)
            else:
                # Manual mode - start regular macros and set up trigger
                self.runner.start(regular_macros)
                self.setup_manual_trigger()
        else:
            self.runner.start(regular_macros)
        
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
        self.stop_manual_trigger()
        self.status.setText("Stopped")
    
    def setup_manual_trigger(self):
        trigger_key1 = self.center_alignment["center_config"]["trigger_key1"]
        trigger_key2 = self.center_alignment["center_config"]["trigger_key2"]
        
        def on_trigger1():
            if self.runner.running:
                self.runner.fire_center_alignment(1)  # Fire Left Right (,.) pattern
        
        def on_trigger2():
            if self.runner.running:
                self.runner.fire_center_alignment(2)  # Fire Right Left (.,) pattern
        
        try:
            if self.manual_trigger_listener:
                self.manual_trigger_listener.stop()
        except:
            pass
        
        # Format keys properly for GlobalHotKeys
        def format_key(key):
            if key.startswith('f') and len(key) <= 3 and key[1:].isdigit():
                return f"<{key}>"
            return key
        
        self.manual_trigger_listener = GlobalHotKeys({
            format_key(trigger_key1): on_trigger1,
            format_key(trigger_key2): on_trigger2
        })
        self.manual_trigger_listener.start()
    
    def stop_manual_trigger(self):
        try:
            if self.manual_trigger_listener:
                self.manual_trigger_listener.stop()
                self.manual_trigger_listener = None
        except:
            pass

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
    
    def edit_center_alignment(self, entry):
        dlg = CenterAlignmentDialog(self.center_alignment["center_config"], self)
        if dlg.exec():
            self.center_alignment["center_config"] = dlg.get_config()
            self.refresh_list()
            self.save_config()

    # ---------- REMOVE ----------
    def remove_selected(self):
        row = self.list_widget.currentRow()
        if row == 0:
            QMessageBox.warning(self, "Cannot Delete", "Center Alignment macro cannot be deleted.")
            return
        if row > 0:
            self.macros.pop(row - 1)  # -1 because center alignment is at index 0
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
                self.center_alignment = data.get("center_alignment", self.center_alignment)
                self.refresh_list()
        except FileNotFoundError:
            pass

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "start_key": self.start_key,
                "stop_key": self.stop_key,
                "pause_key": self.pause_key,
                "center_alignment": self.center_alignment,
                "macros": self.macros
            }, f, indent=2)

    def closeEvent(self, event):
        self.runner.stop()
        self.stop_manual_trigger()
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
