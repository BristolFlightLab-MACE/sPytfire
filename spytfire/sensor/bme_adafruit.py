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

import adafruit_bme280.basic as adafruit_bme280

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
            I2C multiplexer exposing the selected channel.

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

            _ , i2caddress = address

            self.sensor = adafruit_bme280.Adafruit_BME280_I2C(
                i2cbus,
                address=i2caddress
            )

        except Exception as exc:
            print(f"[{name}] Hardware failure: {exc}")
            self.sensor = None
            return
        
        self.consecutive_failures = 0
        self.MAX_ALLOWED_FAILURES = 5
        
        self.initialized = True
        
    def process(self):
        try:
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