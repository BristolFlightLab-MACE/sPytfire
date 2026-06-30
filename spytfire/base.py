# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 11:39:00 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""

# Import pyside6 to create the process for reading data in to an application
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QCoreApplication, Qt

# Import random to provide random inputs for the demonstration SensorWorker
import random

# Provides some useful time options
from datetime import datetime, timezone

# Allow timestamping immediately upon data acquisition
import time

class BaseWorker(QObject):
    finished = Signal()
    stop_requested = Signal()

    def __init__(self, name):
        super().__init__()
        self.initialized = False
        self.name = name
        
        # Force QueuedConnection so the stop() slot runs on the worker thread
        self.stop_requested.connect(self.stop_work, type=Qt.QueuedConnection)

    """Override this in subclasses!"""
    def start_work(self):
        raise NotImplementedError()
    
    
    def timestamp(self):
        """Returns the current time in nanoseconds from the connected."""
        return time.monotonic_ns()

    @Slot()
    def stop_work(self):
        pass
        
    def _safe_shutdown(self,reason="Unknown Error"):   
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")
        
        self.initialized = False

class BasePollingWorker(BaseWorker):
    """Handles workers that require a constant heartbeat timer (Sensors)."""
    def __init__(self, name, interval_ms=100):
        super().__init__(name)
        self.interval_ms = interval_ms
        self.timer = None

    def start_work(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process)
        self.destroyed.connect(self.timer.deleteLater)
        self.timer.start(self.interval_ms)
        
    def process(self):
        raise NotImplementedError("Subclasses must implement process()")

    @Slot()
    def stop_work(self):
        if self.timer:
            self.timer.stop()
            self.timer = None

# This is the basic structure of a SensorWorker
class SensorWorker(BasePollingWorker):
    data_ready = Signal(str, dict)
    
    def __init__(self, name, interval_ms=100):
        """
        Simulate a completed BasePollingWorker to demonstrate how a sensor
        worker can interface with the base class.

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use
        interval_ms : int, optional (Default is 100 ms)
            Provided the repolling time between each measurement start

        Attributes
        ----------
        initialized : bool
            Value that can be read outside the class to monitor the connection
        
        Emits
        ----------
        data_ready : dictionary
            A dictionary object containing a randomly generated number and the 
            sensor payload computer timestamp

        """   
        # Pass shared variables to BaseWorker
        super().__init__(name, interval_ms)
        self.initialized = True

    def process(self):
        # Your specific sensor logic here
        data = {'value': random.random(),
                'time' : self.timestamp()}
        self.data_ready.emit(self.name, data)
        
# ---------------- Time Worker ----------------
# The Time Worker
class UASWorker(BaseWorker):
    data_ready = Signal(str)
    
    def __init__(self, name):
        # We pass interval_ms up, but we won't use it
        super().__init__(name)
        self.initialized = True

    @Slot(int)
    def update_from_mavlink(self, unix_usec):
        """Processes and immediately emits data the millisecond it arrives."""
        try:
            dt = datetime.fromtimestamp(unix_usec / 1_000_000.0, tz=timezone.utc)
        except (ValueError, OverflowError):
            return
        
        if dt.year >= 2025:
            time_string = dt.strftime('%H:%M:%S.%f')
            # Directly emit the time update from Mavlink to sPytfire main
            self.data_ready.emit(time_string)