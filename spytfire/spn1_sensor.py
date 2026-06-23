# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 11:29:30 2026

This module codes the operation of the Apogee SL-510 and SL-610 thermopile 
pygeometers and SP-510 and SP-610 pyronometers

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

# Import numpy for calculating the longwave and shortwave results from the 
# apogee sensors
import numpy as np

# Can connect to SPN1 over both serial and analogue. We chose serial here
import serial

import time

class SPN1SensorWorker(BasePollingWorker):
    '''Class to read the Delta-T SPN1 and emit it to the controller.'''
    data_ready = Signal(str, dict)
    
    def __init__(self, name, interval_ms=200):
        
        # Pass shared variables to BaseWorker
        super().__init__(name, interval_ms)
        
        #PORT = 'COM5'                        # port when connected to my laptop
        PORT = "/dev/ttyUSB0"                 # port when connected to pi  
        try:
            # Establish Serial connection
            self.ser = serial.Serial(PORT, 9600, timeout=2)
            
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
            #self.ser.write(b'?') # Shows possible commands
            self.ser.write(b'F') # Dumps data
            
            while self.ser.in_waiting == 0 and runtime < 5:
                curr = time.time()
                runtime = curr-start
                time.sleep(0.01)
                
            if runtime >= 5:
                self._safe_shutdown()
            
            # Read raw binary input from SPN1 device
            raw = self.ser.readline(self.ser.in_waiting)
            
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
                         'timestamp'    :now
                         }            

            self.data_ready.emit(self.name, spn1_dict)
            
        except Exception as e:
            print(f"SPN1 Read Error: {e}")
            
    def _safe_shutdown(self, reason="Unknown Error"):
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")
            
        if hasattr(self, 'ser') and self.ser is not None:
            try:
                self.ser.close()
            except Exception as shutdown_err:
                print(f"[{self.name}] Serial control failed: {shutdown_err}")
        else:
            print(f"[{self.name}] Cannot disable hardware: Connection reference is missing")
            
        self.initialized = False