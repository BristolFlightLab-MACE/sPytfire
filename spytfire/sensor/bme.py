# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 12:04:52 2026

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================

from dataclasses import dataclass, asdict

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

@dataclass(frozen=True)
class BMESample:
    """A simple container for a single BME280 sample."""
    temperature: float
    pressure: float
    humidity: float
    timestamp_ns: int

# =============================================================================

class BMESensorWorker(BasePollingWorker):
    '''Class to read a BME280 and emit the data to the controller.'''
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, address = None, interval_ms=200, i2cbus=None):
        """
        Connect to and operate a BME280 environmental sensor.

        Parameters
        ----------
        name : string
            Unique identifier for the sensor instance.
        serial_num : string, optional
            Device serial number, if available. Not used by this sensor.
        address : tuple
            ``(mux_channel, i2c_address)`` for the BME280.
        interval_ms : int, optional
            Polling interval between measurements, in milliseconds.
        i2cbus : object, optional
            Accepted for the shared worker interface; this implementation
            uses its own SMBus connection.

        Attributes
        ----------
        sensor : 
            The Pimoroni BME280 I2C connection is held by this attribute
        is_initialized : bool
            Value that can be read outside the class to monitor the connection
        
        Emits
        ----------
        data_ready : dict
            Temperature, pressure, humidity, and acquisition timestamp.

        """     
        # Pass shared variables to BasePollingWorker
        super().__init__(name, serial_num, address, interval_ms)
        
        try:
            self.bus = SMBus(1)

            self.channel, i2caddress = address

            self.bus.write_byte(0x70, 1 << self.channel) # 1 << channel means send a single on bit to the right position

            self.sensor = BME280(i2c_dev=self.bus)
            self.sensor.update_sensor() 
            
        except (NameError,ValueError, OSError, RuntimeError) as exc:
            print(f"[{name}] Hardware failure: {exc}")
            self.sensor = None
            return
        
        self.consecutive_failures = 0
        self.MAX_ALLOWED_FAILURES = 5
        
        self.initialized = True
        
    def process(self):
        try:
            ### CURRENT SETUP VULNERABLE TO RACE CONDITIONS
            self.bus.write_byte(0x70, 1 << 1) # to ensure the multiplexer channel line is open for the bme280
            self.sensor.update_sensor() 

            sample = BMESample(
                temperature=self.sensor.temperature,
                pressure=self.sensor.pressure,
                humidity=self.sensor.humidity,
                timestamp_ns=self.timestamp()
            )
            
            self.data_ready.emit(self.name, 'pim_bme280', asdict(sample))
            self.consecutive_failures = 0
            
        except (Exception, RuntimeError) as exc:
            print(f"BME280 Read Error: {exc}")
            self.consecutive_failures += 1
            
            if self.consecutive_failures >= self.MAX_ALLOWED_FAILURES:
                self._safe_shutdown(reason="Repeated Data Corruption/Key Errors")
            