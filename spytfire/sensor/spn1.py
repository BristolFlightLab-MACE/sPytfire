# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 11:29:30 2026

This module codes the operation of the Apogee SL-510 and SL-610 thermopile 
pygeometers and SP-510 and SP-610 pyronometers

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# =============================================================================
# Define imports
# =============================================================================

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

# Import numpy for calculating the longwave and shortwave results from the 
# apogee sensors
import numpy as np

# Can connect to SPN1 over both serial and analogue. We chose serial here
import serial

# Use time to add delays in loops to prevent overloading of a looped function
import time

# =============================================================================
# Create new SensorWorker for the delta-T SPN1
# =============================================================================

class SPN1SensorWorker(BasePollingWorker):
    '''Class to read the Delta-T SPN1 and emit it to the controller.'''
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, interval_ms=200):
        """
        A BasePollingWorker to connect and operate a delta-T SPN1
        sunshine pyronometer to measure the total and diffuse solar 
        irradiance in a volcanic plume.

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use
        interval_ms : int, optional (Default is 200 ms)
            Provided the repolling time between each measurement start

        Attributes
        ----------
        sensor : 
            The SPN1 connection is held by this attribute
        is_initialized : bool
            Value that can be read outside the class to monitor the connection

        Emits
        ----------
        data_ready : dictionary
            A dictionary object containing information on the direct and total
            irradiation measured by the spn1, a determined 'cloudiness' boolean
            and the sensor payload computer timestamp

        """   
        
        # Pass shared variables to BasePollingWorker
        super().__init__(name, serial_num, interval_ms)
        
        #PORT = 'COM5'                        # port when connected to my laptop
        PORT = "/dev/ttyUSB0"                 # port when connected to pi  
        try:
            # Establish Serial connection
            self.sensor = serial.Serial(PORT, 9600, timeout=2)
            
        except (NameError, serial.SerialException) as e:
            print(f"[{name}] Hardware failure: {e}")
            self.sensor = None
            return
        
        time.sleep(1)
        
        self.initialized = True
    
    def process(self):
        try:
            start = time.time()
            runtime = 0
            
            # Transmit data over serial connection
            #self.sensor.write(b'?') # Shows possible commands
            self.sensor.write(b'F') # Dumps data
            
            while self.sensor.in_waiting == 0 and runtime < 5:
                curr = time.time()
                runtime = curr-start
                time.sleep(0.01)
                
            if runtime >= 5:
                self._safe_shutdown()
            
            # Read raw binary input from SPN1 device
            raw = self.sensor.readline(self.sensor.in_waiting)
            
            # Decode ascii characters
            decode = raw.decode('ascii', errors='ignore').strip()
            
            # Quick check to make sure data has correct starting number
            if decode.startswith('F'):
                parts = [p.strip() for p in decode.split(',')]
                
                total   = float(parts[0][1:])
                diffuse = float(parts[1])
                sun     = int(parts[2])
                case_t  = float(parts[-2])
                now     = self.timestamp()  

            spn1_dict = {'total'        : total,
                         'diffuse'      : diffuse,
                         'sun_state'    : sun,
                         'case_temp'    : case_t,
                         'timestamp'    : now
                         }            

            self.data_ready.emit(self.name, 'spn1', spn1_dict)
            
        except Exception as e:
            print(f"SPN1 Read Error: {e}")
            
    def _safe_shutdown(self, reason="Unknown Error"):
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")
            
        if hasattr(self, 'sensor') and self.sensor is not None:
            try:
                self.sensor.close()
            except Exception as shutdown_err:
                print(f"[{self.name}] Serial control failed: {shutdown_err}")
        else:
            print(f"[{self.name}] Cannot disable hardware: Connection reference is missing")
            
        self.initialized = False