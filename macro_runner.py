import threading
import time
from pynput.keyboard import Controller, Key
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
        self.running = False
        self.center_thread = None
    
    def start(self, macros):
        self.stop()
        self.stop_event.clear()
        self.pause_event.set()
        self.paused = False
        self.running = True
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
    
    def start_with_center(self, macros, center_config):
        """Start macros with auto center alignment"""
        self.start(macros)
        
        # Start center alignment in auto mode
        self.center_thread = threading.Thread(
            target=self._run_center_auto,
            args=(center_config,),
            daemon=True
        )
        self.center_thread.start()
        self.threads.append(self.center_thread)
    
    def _run_center_auto(self, center_config):
        """Run center alignment in auto mode"""
        try:
            interval = center_config["center_config"]["interval"]
            
            while not self.stop_event.is_set():
                self.pause_event.wait()
                
                if self.stop_event.is_set():
                    return
                
                # Countdown
                start = time.monotonic()
                end = start + interval
                
                while True:
                    self.pause_event.wait()
                    
                    if self.stop_event.is_set():
                        return
                    
                    now = time.monotonic()
                    remaining = end - now
                    
                    if remaining <= 0:
                        break
                    
                    self.tick.emit("_center_", remaining)
                    time.sleep(0.05)
                
                # Fire center alignment sequence
                self._fire_center_sequence()
                self.fired.emit("_center_")
        
        except Exception as e:
            print(f"Error in center alignment auto: {e}")
    
    def fire_center_alignment(self):
        """Manually trigger center alignment (for manual mode)"""
        if not self.running or self.stop_event.is_set():
            return
        
        threading.Thread(target=self._fire_center_sequence, daemon=True).start()
        self.fired.emit("_center_")
    
    def _fire_center_sequence(self):
        """Execute the center alignment key sequence: , wait 50ms ."""
        try:
            # Press ,
            self.keyboard.press(',')
            self.keyboard.release(',')
            
            # Wait 50ms
            time.sleep(0.05)
            
            # Press .
            self.keyboard.press('.')
            self.keyboard.release('.')
        except Exception as e:
            print(f"Error firing center sequence: {e}")
    
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
        self.running = False
        self.stop_event.set()
        self.pause_event.set()
        
        # Wait for all threads to finish
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1)
        
        self.threads = []
        self.center_thread = None
        self.stopped.emit()
