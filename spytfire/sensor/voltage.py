# -*- coding: utf-8 -*-
"""
Created on Fri Apr 17 13:45:04 2026

This module codes the operation of the voltage sensor for the analogue apogee
sensors. It's structure is very similar to the analogue apogee sensor structure

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

# Import modules for apogee sensors
try:
    import board
except NotImplementedError:
    print("Hardware not detected. Running in Simulation Mode.")
    
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

# =============================================================================
# Create new SensorWorker for the internal voltage ADS1115
# =============================================================================

class VoltageSensorWorker(BasePollingWorker):
    '''Class to read the excitation voltage from the ADC and emit it to the controller.'''
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, interval_ms=200):
        """
        A BasePollingWorker that replicates the structure of
        apogee_sensor.py to use an adafruit ADS1115 to measure the 
        differential voltage that is placed across apogee longwave
        sensors.

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use
        interval_ms : int, optional (Default is 200 ms)
            Provided the repolling time between each measurement start

        Attributes
        ----------
        sensor : 
            The Adafruit ADS1115 I2C connection is held by this attribute
        is_initialized : bool
            Value that can be read outside the class to monitor the connection
        
        Emits
        ----------
        data_ready : dictionary
            A dictionary object containing the sensor payload computer 
            timestamp and the differential voltage across the apogee sensors

        """   
        
        # Pass shared variables to BasePollingWorker
        super().__init__(name, serial_num, interval_ms)
        
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
            
            self.data_ready.emit(self.name, 'voltage', voltage_dict)
            
        except Exception as e:
            print(f"Voltage Read Error: {e}")