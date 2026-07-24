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

import time

# Import modules for apogee sensors
try:
    import board
except NotImplementedError:
    print("Hardware not detected. Running in Simulation Mode.")

from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

# =============================================================================
# Create new SensorWorker for controlling alphasense gas sensors
# =============================================================================

class GasSensorWorker(BasePollingWorker):
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, interval_ms=100):
        """
        Simulate a completed BasePollingWorker to demonstrate how a sensor
        worker can interface with the base class.

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use. Set to be the
            serial number if available
        interval_ms : int, optional (Default is 100 ms)
            Provided the repolling time between each measurement start

        Attributes
        ----------
        is_initialized : bool
            Value that can be read outside the class to monitor the connection
        
        Emits
        ----------
        data_ready : dictionary
            A dictionary object containing a randomly generated number and the 
            sensor payload computer timestamp

        """   
        # Pass shared variables to BaseWorker
        super().__init__(name, serial_num, interval_ms)

        try:
            # Create the I2C bus
            i2c = board.I2C()
            
            address = 0x48
            address = 0x49

            # Create the ADC object using the I2C bus
            self.sensor = ADS1115(i2c, address = address)

            self.channel = AnalogIn(self.channel, 0, 1)

        except (NameError, ValueError, OSError, AttributeError) as e:
            print(f"[{self.name}] Hardware failure: {e}")
            
            if hasattr(self, 'i2c') and self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass
            return  

        self.initialized = True

    def process(self):
        _ = self.channel.voltage
        time.sleep(0.01)
        mvolt = self.channel.voltage * 1000

        conc = (mvolt + self.zeroAE - self.zeroWE)/self.sens

        # Your specific sensor logic here
        data = {'mvolt': mvolt,
                'conc' : conc,
                'timestamp' : self.timestamp()}
        self.data_ready.emit(self.name, 'gas', data)

    def _safe_shutdown(self,reason="Unknown Error"):   
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")

        # CLEANUP: If the bus was created but sensor failed, release the bus
            if hasattr(self, 'i2c') and self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass 
            self.sensor = None
        
        self.initialized = False