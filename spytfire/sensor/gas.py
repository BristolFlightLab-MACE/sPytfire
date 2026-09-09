"""
Created on Tue Mar 31 11:29:30 2026

This module codes the operation of the Apogee SL-510 and SL-610 thermopile 
pygeometers and SP-510 and SP-610 pyronometers

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================

from dataclasses import dataclass, asdict

from numpy.matlib import identity

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

import time

# Import modules for gas sensors
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

@dataclass(frozen=True)
class GasSample:
    """A simple container for a single gas sensor sample."""
    mvolt: float
    identity: str
    conc: float
    timestamp_ns: int

# =============================================================================

class GasSensorWorker(BasePollingWorker):
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, address = None, interval_ms=100, i2cbus = None):
        """
        Connect to and operate an Alphasense gas sensor through an ADS1115.

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
            Gas sensor voltage, identity, concentration, and timestamp.

        """   
        # Pass shared variables to BaseWorker
        super().__init__(name, serial_num, address, interval_ms)

        try:
            _ , i2caddress = address

            # Create the ADC object using the I2C bus
            self.sensor = ADS1115(i2cbus, address = i2caddress)

            # Create differential input between channel 0 and 1
            self.chan1 = AnalogIn(self.sensor, ads1x15.Pin.A0, ads1x15.Pin.A1)

            # Create differential input between channel 2 and 3
            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A2, ads1x15.Pin.A3)

        except (NameError, ValueError, OSError, AttributeError, TypeError) as exc:
            print(f"[{self.name}] Hardware failure: {exc}")
            
            if hasattr(self, 'i2c') and self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass
            return  

        self.initialized = True

    def get_params(self, identity):

        if identity in ('HCl_B1', 'HCl-B1'):
            params = ({
                "shunt_ohms": 219.2,
                "maximum_ppm": 100,
                "minimum_ppm": 0,
                "min_current_ma": 4.0,
                "max_current_ma": 20.0
            })

        elif identity in ('IRC-A1', 'IRC_A1'):
            params = ({
                "shunt_ohms": 219.4,
                "maximum_ppm": 5000,
                "minimum_ppm": 0,
                "min_current_ma": 4.0,
                "max_current_ma": 20.0
            })

        else:
            print('Issue with serial_num')
            return None

        return params
    
    def process(self):

        try:
            mvolt0, timestamp0 = self.measure_mv(self.chan0)
            mvolt1, timestamp1 = self.measure_mv(self.chan1)

            conc0 = self.calc_conc(mvolt0,self.serial_num[0])
            conc1 = self.calc_conc(mvolt1,self.serial_num[1])

            sample0 = GasSample(
                mvolt=mvolt0,
                identity = 'CO2',
                conc=conc0,
                timestamp_ns=timestamp0
            )

            sample1 = GasSample(
                mvolt=mvolt1,
                identity = 'HCl',
                conc=conc1,
                timestamp_ns=timestamp1
            )

            # Emit data in slot
            self.emit_data(sample0)
            self.emit_data(sample1)

        except Exception as exc:
            self._safe_shutdown(reason = exc)

    def measure_mv(self,channel):

        # Clean ADC memory for more accurate second read
        _ = channel.voltage
        time.sleep(0.01)

        # Perform voltage reading
        mvolt = channel.voltage * 1000

        # Timestamp returning result
        timestamp = self.timestamp()
        time.sleep(0.01)

        return(mvolt,timestamp)

    def calc_conc(self,v_diff,identity):
        params = self.get_params(identity)
        if params is None:
            raise ValueError(f"Unknown sensor type: {identity}")

        current_ma = (v_diff / params["shunt_ohms"])

        if identity in ("HCl-B1", "HCl_B1","IRC-A1", "IRC_A1"):
            conc = (current_ma-params["min_current_ma"])*((params["maximum_ppm"]-params["minimum_ppm"])/(params["max_current_ma"]-params["min_current_ma"])) + params["minimum_ppm"]
        else:
            raise ValueError(f"Unknown sensor type: {identity}")
        
        return conc

    def emit_data(self,sample):        
        self.data_ready.emit(self.name, 'alpha_gas', asdict(sample))

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