"""
Created on Tue Mar 31 11:29:30 2026

This module codes the operation of the Apogee SL-510 and SL-610 thermopile 
pygeometers and SP-510 and SP-610 pyronometers

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

# Import numpy for calculating the longwave and shortwave results from the 
# apogee sensors
import numpy as np

import time

from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

# =============================================================================

class AFESensorWorker(BasePollingWorker):
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, address = None, interval_ms=100, i2cbus=None):
        """
        Connect to and operate an Alphasense AFE gas sensor through an ADS1115.

        Parameters
        ----------
        name : string
            Unique identifier for the sensor instance.
        serial_num : string or list, optional
            Gas sensor serial number(s), if available.
        address : tuple
            ``(mux_channel, i2c_address)`` for the ADS1115.
        interval_ms : int, optional
            Polling interval between measurements, in milliseconds.
        i2cbus : object, optional
            I2C multiplexer exposing the selected channel.

        Attributes
        ----------
        is_initialized : bool
            Value that can be read outside the class to monitor the connection
        
        Emits
        ----------
        data_ready : dict
            Gas sensor voltage, concentration, and acquisition timestamp.

        """   
        # Pass shared variables to BaseWorker
        super().__init__(name, serial_num, address, interval_ms)

        try:          
            _ , i2caddress = address
            # Create the ADC object using the I2C bus
            self.sensor = ADS1115(i2cbus, address = i2caddress)

            self.chan = AnalogIn(self.chan, 0, 1)

        except (NameError, ValueError, OSError, AttributeError, TypeError) as exc:
            print(f"[{self.name}] Hardware failure: {exc}")
            
            if hasattr(self, 'i2c') and self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass
            return  

        self.initialized = True

    def process(self):
        _ = self.chan.voltage
        time.sleep(0.01)
        mvolt = self.chan.voltage * 1000

        conc = (mvolt + self.zeroAE - self.zeroWE)/self.sens

        # Your specific sensor logic here
        data = {'mvolt': mvolt,
                'name' : 'O3',
                'conc' : conc,
                'timestamp_ns' : self.timestamp()}
        self.data_ready.emit(self.name, 'alpha_gas', data)

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