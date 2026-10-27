"""
Created on Tue Mar 31 11:29:30 2026

This module codes the operation of the Apogee SL-510 and SL-610 thermopile 
pygeometers and SP-510 and SP-610 pyronometers

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================
from dataclasses import dataclass, asdict

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
def calc_pt1000_temperature(mvolt_mV):

    # Using alphasense equations for equation 1
    temperature_eq1 = (mvolt_mV/1000 - 0.297)/0.001
    '''
    This is a method to calculate the temperature from a PT1000 sensor assuming
    it is in a voltage divider configuration. Alphasense insist this is not the
    case, as they maintain the voltage provided to the PT1000 is not constant.

    # Assuming differential voltage between 7320 ohm resistor and PT1000 sensor
    resistance = ((mvolt_mV/1000)*7320)/(2.5-mvolt_mV/1000)

    # Callendar-Van Dusen equation for PT1000, the coefficients are:
    A = 3.9083e-3
    B = -5.775e-7
    C = -4.183e-12  # Only used for temperatures below 0°C

    if resistance >= 1000:  # Above 0°C
        temperature_eq2 = (-A + np.sqrt(A**2 - 4*B*(1 - resistance/1000))) / (2*B)
    else:  # Below 0°C
        raise ValueError("Temperature below 0°C not supported in this implementation.")
    '''
    return temperature_eq1

@dataclass(frozen=True)
class PT1000Sample:
    """A simple container for a single gas sensor sample."""
    mvolt_mV: float
    name: str
    temperature_C: float
    timestamp_ns: int

class PT1000SensorWorker(BasePollingWorker):
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

            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0,ads1x15.Pin.A1)

        except (NameError, ValueError, OSError, AttributeError, TypeError) as exc:
            print(f"[{self.name}] Hardware failure: {exc}")
            
            if hasattr(self, 'sensor') and self.sensor:
                try:
                    self.sensor.deinit()
                except:
                    pass
            return  

        self.initialized = True

    def measure_channel(self, channel):
        _ = channel.voltage
        time.sleep(0.01)
        mvolt = channel.voltage * 1000
        return mvolt

    def process(self):
        mvolt = self.measure_channel(self.chan0)
        temperature = calc_pt1000_temperature(mvolt)

        sample = PT1000Sample(
            mvolt_mV = mvolt,
            name = self.name,
            temperature_C = temperature,
            timestamp_ns = self.timestamp()
        )

        self.data_ready.emit(self.name, 'pt1000', asdict(sample))
        
    def _safe_shutdown(self,reason="Unknown Error"):   
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")

        # CLEANUP: If the bus was created but sensor failed, release the bus
            if hasattr(self, 'sensor') and self.sensor:
                try:
                    self.sensor.deinit()
                except:
                    pass 
            self.sensor = None
        
        self.initialized = False