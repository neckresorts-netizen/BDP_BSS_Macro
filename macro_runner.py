import time
import threading
from pynput.keyboard import Controller, Key

keyboard = Controller()


def normalize_key(key):
    if len(key) == 1:
        return key
    try:
        return getattr(Key, key)
    except AttributeError:
        return None


class MacroRunner:
    def __init__(self):
        self.running = False
        self.thread = None

    def start(self, macro):
        if self.running or not macro:
            return

        self.running = True

        def run():
            while self.running:
                for entry in macro:
                    if not self.running:
                        break

                    key = normalize_key(entry["key"])
                    delay = entry["delay"]
                    repeat = entry.get("repeat", -1)

                    if key is None:
                        continue

                    count = repeat if repeat > 0 else float("inf")

                    for _ in range(int(count)):
                        if not self.running:
                            break

                        try:
                            keyboard.press(key)
                            keyboard.release(key)
                        except Exception:
                            pass

                        time.sleep(delay)

                if not any(e.get("repeat", -1) < 0 for e in macro):
                    break

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
