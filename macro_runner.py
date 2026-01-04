import threading
import time
from pynput.keyboard import Controller
from PySide6.QtCore import QObject, Signal


class MacroRunner(QObject):
    tick = Signal(str, float)   # key, seconds remaining
    fired = Signal(str)
    stopped = Signal()
    
    def __init__(self):
        super().__init__()
        self.keyboard = Controller()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.threads = []
        self.paused = False
    
    def start(self, macros):
        self.stop()
        self.stop_event.clear()
        self.pause_event.set()
        self.paused = False
        self.threads = []
        
        # Start a separate thread for each enabled macro
        for m in macros:
            if not m.get("enabled", True):
                continue
            
            thread = threading.Thread(
                target=self._run_macro,
                args=(m,),
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
    
    def _run_macro(self, m):
        """Run a single macro in its own thread"""
        try:
            key = m["key"]
            delay = float(m["delay"])
            repeat = m["repeat"]
            count = 0
            
            while repeat < 0 or count < repeat:
                self.pause_event.wait()
                
                if self.stop_event.is_set():
                    return
                
                start = time.monotonic()
                end = start + delay
                
                # Countdown
                while True:
                    self.pause_event.wait()
                    
                    if self.stop_event.is_set():
                        return
                    
                    now = time.monotonic()
                    remaining = end - now
                    
                    if remaining <= 0:
                        break
                    
                    self.tick.emit(key, remaining)
                    time.sleep(0.05)
                
                # Fire key ONCE
                try:
                    self.keyboard.press(key)
                    self.keyboard.release(key)
                except Exception:
                    pass
                
                self.fired.emit(key)
                count += 1
        
        except Exception as e:
            print(f"Error in macro {m.get('name', 'unknown')}: {e}")
    
    def pause(self):
        self.paused = True
        self.pause_event.clear()
    
    def resume(self):
        self.paused = False
        self.pause_event.set()
    
    def stop(self):
        self.stop_event.set()
        self.pause_event.set()
        
        # Wait for all threads to finish
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1)
        
        self.threads = []
        self.stopped.emit()
