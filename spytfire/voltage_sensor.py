# -*- coding: utf-8 -*-
"""
Created on Fri Apr 17 13:45:04 2026

This module codes the operation of the voltage sensor for the analogue apogee
sensors. It's structure is very similar to the analogue apogee sensor structure

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk

"""

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

# Import modules for apogee sensors
try:
    import board
except NotImplementedError:
    print("Hardware not detected. Running in Simulation Mode.")
    
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

class VoltageSensorWorker(BasePollingWorker):
    data_ready = Signal(str, dict)
    
    def __init__(self, name, interval_ms=200):
        
        # Pass shared variables to BaseWorker
        super().__init__(name, interval_ms)
        
        try:
            # Create the I2C bus
            i2c = board.I2C()
            
            address = 74
            
            # Create the ADC object using the I2C bus
            self.ads = ADS1115(i2c,address = address)
        
        except (NameError, ValueError, OSError, AttributeError) as e:
            print(f"[{name}] Hardware failure: {e}")
            self.sensor = None
            return
            
        # Create differential input between channel 0 and 1
        self.chan0 = AnalogIn(self.ads, ads1x15.Pin.A0, ads1x15.Pin.A1)
        
        # Isolate the name of the device so that the calibration coefficents
        # can be used
        self.model = name
        
        self.initialized = True
        
    def process(self):
        try:
            v0 = self.chan0.voltage
            
            voltage_dict = {'excite_v': v0,
                            'timestamp': self.timestamp()
                          }
            
            self.data_ready.emit(self.name, voltage_dict)
            
        except Exception as e:
            print(f"Voltage Read Error: {e}")