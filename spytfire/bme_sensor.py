# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 12:04:52 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

# Import modules for BME280
try:
    from smbus2 import SMBus
except ModuleNotFoundError:
    print("Windows machine detected. Running in Simulation Mode.")    

from bme280 import BME280

class BMESensorWorker(BasePollingWorker):
    data_ready = Signal(str, dict)
    
    def __init__(self, name, interval_ms=200):
        """
        A BasePollingWorker to connect and operate a BME280 environment
        sensor that measures surrounding temperature, pressure and 
        humidity.

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use
        interval_ms : int, optional (Default is 200 ms)
            Provided the repolling time between each measurement start

        Attributes
        ----------
        sensor : 
            The Pimoroni BME280 I2C connection is held by this attribute
        is_initialized : bool
            Value that can be read outside the class to monitor the connection
        
        Emits
        ----------
        data_ready : dictionary
            A dictionary object containing information on the temperature,
            pressure and humidity measured as well as the sensor payload 
            computer timestamp

        """     
        # Pass shared variables to BaseWorker
        super().__init__(name, interval_ms)
        
        try:
            self.bus = SMBus(1)
            self.sensor = BME280(i2c_dev=self.bus)
            self.sensor.update_sensor() 
            
        except (NameError,ValueError, OSError, RuntimeError) as e:
            print(f"[{name}] Hardware failure: {e}")
            self.sensor = None
            return
        
        self.consecutive_failures = 0
        self.MAX_ALLOWED_FAILURES = 5
        
        self.initialized = True
        
    def process(self):
        try:
            self.sensor.update_sensor() 
            
            bme_dict = {'temperature': self.sensor.temperature,
                        'pressure': self.sensor.pressure,
                        'humidity': self.sensor.humidity,
                        'timestamp': self.timestamp()
                        }
            
            self.data_ready.emit(self.name, bme_dict)
            self.consecutive_failures = 0
            
        except (Exception, RuntimeError) as e:
            print(f"BME280 Read Error: {e}")
            self.consecutive_failures += 1
            
            if self.consecutive_failures >= self.MAX_ALLOWED_FAILURES:
                self._safe_shutdown(reason="Repeated Data Corruption/Key Errors")
            