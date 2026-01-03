import time
from pynput.keyboard import Controller as KeyboardController

keyboard = KeyboardController()

class MacroRunner:
    def __init__(self):
        self.running = False
        self.macro = []

    def set_macro(self, macro):
        self.macro = macro

    def start(self):
        self.running = True
        while self.running:
            for entry in self.macro:
                if not self.running:
                    break
                key = entry["key"]
                delay = entry["delay"] / 1000
                keyboard.press(key)
                keyboard.release(key)
                time.sleep(delay)

    def stop(self):
        self.running = False
