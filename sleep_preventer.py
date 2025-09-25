import ctypes
import threading
import time
from ctypes import wintypes

class SleepPreventer:
    """Prevents Windows from sleeping during MIDI activity"""
    
    def __init__(self):
        self.is_preventing_sleep = False
        self.last_activity_time = 0
        self.activity_timeout = 300  # 5 minutes of inactivity before allowing sleep
        self.monitor_thread = None
        self.monitor_running = False
        
        # Windows API constants
        self.ES_CONTINUOUS = 0x80000000
        self.ES_SYSTEM_REQUIRED = 0x00000001
        self.ES_DISPLAY_REQUIRED = 0x00000002
        
        try:
            # Get Windows kernel32 functions
            self.kernel32 = ctypes.windll.kernel32
            self.kernel32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
            self.kernel32.SetThreadExecutionState.restype = wintypes.DWORD
            self.available = True
        except Exception as e:
            print(f"Sleep prevention not available: {e}")
            self.available = False
    
    def start_monitoring(self):
        """Start the sleep prevention monitoring"""
        if not self.available:
            return False
            
        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_activity, daemon=True)
        self.monitor_thread.start()
        return True
    
    def stop_monitoring(self):
        """Stop monitoring and allow normal sleep"""
        self.monitor_running = False
        self._allow_sleep()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
    
    def register_activity(self):
        """Call this when MIDI activity is detected"""
        self.last_activity_time = time.time()
        if not self.is_preventing_sleep:
            self._prevent_sleep()
    
    def _prevent_sleep(self):
        """Prevent system from sleeping"""
        if not self.available:
            return
            
        try:
            # Prevent system sleep and keep display on
            result = self.kernel32.SetThreadExecutionState(
                self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_DISPLAY_REQUIRED
            )
            if result != 0:
                self.is_preventing_sleep = True
                print("Sleep prevention enabled")
            else:
                print("Failed to prevent sleep")
        except Exception as e:
            print(f"Error preventing sleep: {e}")
    
    def _allow_sleep(self):
        """Allow system to sleep normally"""
        if not self.available or not self.is_preventing_sleep:
            return
            
        try:
            # Restore normal power management
            result = self.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            if result != 0:
                self.is_preventing_sleep = False
                print("Sleep prevention disabled - system can sleep normally")
        except Exception as e:
            print(f"Error allowing sleep: {e}")
    
    def _monitor_activity(self):
        """Monitor for inactivity and allow sleep after timeout"""
        while self.monitor_running:
            try:
                current_time = time.time()
                
                # If we're preventing sleep and there's been no activity for the timeout period
                if (self.is_preventing_sleep and 
                    self.last_activity_time > 0 and 
                    current_time - self.last_activity_time > self.activity_timeout):
                    
                    self._allow_sleep()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                print(f"Sleep monitor error: {e}")
                time.sleep(10)