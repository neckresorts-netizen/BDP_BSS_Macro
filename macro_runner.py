import threading
import time
from pynput.keyboard import Controller


class MacroRunner:
    def __init__(self):
        self.running = False
        self.threads = []
        self.keyboard = Controller()

    def start(self, macros):
        if self.running:
            return

        self.running = True
        self.threads = []

        for entry in macros:
            if not entry.get("enabled", True):
                continue  # skip disabled macros

            t = threading.Thread(
                target=self.run_single_macro,
                args=(entry,),
                daemon=True
            )
            self.threads.append(t)
            t.start()

    def stop(self):
        self.running = False

    def run_single_macro(self, entry):
        key = entry["key"]
        delay = entry["delay"]
        repeat = entry.get("repeat", -1)

        if repeat < 0:
            while self.running:
                time.sleep(delay)
                self.press_key(key)
        else:
            for _ in range(repeat):
                if not self.running:
                    return
                time.sleep(delay)
                self.press_key(key)

    def press_key(self, key):
        try:
            self.keyboard.press(key)
            self.keyboard.release(key)
        except Exception:
            pass
