# -*- coding: utf-8 -*-
"""
Created on Tue May 26 20:22:47 2026

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

# Key imports for running alphasense OPC using SPI interface
from usbiss.spi import SPI

# This module is needed if running alphasense OPC using USB interface
#import spidev

import serial

# Libary for operating alphasense OPC
import opcng as opc

import time

# =============================================================================
# Create new SensorWorker for the alphasense OPC-N3
# =============================================================================
class OPCSensorWorker(BasePollingWorker):
    data_ready = Signal(str, dict)
    
    def __init__(self, name, interval_ms=200):
        
        # Pass shared variables to BaseWorker
        super().__init__(name, interval_ms)
        
        try:
            spi = SPI('/dev/ttyACM0')
            #spi = SPI('COM10')
            spi.mode = 1
            spi.max_speed_hz = 500000
            spi.lsbfirst = False

            self.dev = opc.detect(spi)
                        
            self.dev.on()
            
        except (NameError, ValueError, serial.SerialException) as e:
            print(f"[{name}] Hardware failure: {e}")
            
            if hasattr(self,'dev'):
                self.dev.off()
                
            self.sensor = None
            
            return
        
        # Track hardware error states
        self.consecutive_failures = 0
        self.MAX_ALLOWED_FAILURES = 5  # Shut down after ~5 failed attempts
        
        time.sleep(0.6)                # Recommended 600 ms before measurements
        
        self.initialized = True
    
    def process(self):
        try:                
            values = self.dev.histogram()
            
            # Create full list of parameters
            channels = {f'bin{i}': values[f'Bin {i}'] for i in range(24)}
            channels.update({f'bin{i}mtof': values[f'Bin{i} MToF'] for i in [1, 3, 5, 7]})
            channels['sampling_period'] = values['Sampling Period']
            channels['temperature'] = values['Temperature']
            channels['rh'] = values['Relative humidity']
            channels['pm1']   = values['PM1']
            channels['pm2.5'] = values['PM2.5']
            channels['pm10']  = values['PM10']
            channels['sfr']   = values['SFR']
            channels['laser_status'] = values['Laser status']
            channels['timestamp'] = self.timestamp()
            
            self.data_ready.emit(self.name, channels)
            self.consecutive_failures = 0
        
        except (KeyError, ValueError) as data_err:
            # Catch bad dictionary mapping structures or corrupt byte conversions
            self.consecutive_failures += 1
            print(f"[{self.name}] Corrupt data stream format (Error {self.consecutive_failures}/{self.MAX_ALLOWED_FAILURES}): {data_err}")
     
            if self.consecutive_failures >= self.MAX_ALLOWED_FAILURES:
                self._safe_shutdown(reason="Repeated Data Corruption/Key Errors")
        
        except Exception as hardware_err:
            print(f"OPC Read Error: {hardware_err}")
            
            self.consecutive_failures += 1
            
            print(f"[{self.name}] SPI Hardware Error ({self.consecutive_failures}/{self.MAX_ALLOWED_FAILURES}): {hardware_err}")
            
            if self.consecutive_failures >= self.MAX_ALLOWED_FAILURES:
                self.safe_shutdown(reason="Repeated Data Corruption/Key Errors")
    
                
    def _safe_shutdown(self, reason="Unknown Error"):
        """
        Gracefully de-energizes the sensor peripherals to prevent damage.
        """
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")
        
        if hasattr(self, 'dev') and self.dev is not None:
            try:
                # Disables both the internal 658nm laser and the sample fan safely
                self.dev.off()
                print(f"[{self.name}] Laser and Fan powered down successfully.")
                self.dev.close()
            except Exception as shutdown_err:
                print(f"[{self.name}] Hard hardware control failed: {shutdown_err}")
        else:
            print(f"[{self.name}] Cannot disable hardware: Connection reference is missing")
            
        self.initialized = False