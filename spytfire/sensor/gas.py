"""
Created on Tue Mar 31 11:29:30 2026

This module codes the operation of the Apogee SL-510 and SL-610 thermopile 
pygeometers and SP-510 and SP-610 pyronometers

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================
# Define imports
# =============================================================================

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

import time

# Import modules for gas sensors
from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

# =============================================================================
# Create new SensorWorker for controlling alphasense gas sensors
# =============================================================================

class GasSensorWorker(BasePollingWorker):
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, address = None, interval_ms=100, mux = None):
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
        super().__init__(name, serial_num, address, interval_ms)

        try:
            channel, i2caddress, pin_pair = address

            # Create the ADC object using the I2C bus
            self.sensor = ADS1115(mux[channel], address = i2caddress, gain=1)

            # Create differential input between channel 0 and 1
            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0, ads1x15.Pin.A1)
            
            # Create differential input between channel 2 and 3
            self.chan1 = AnalogIn(self.sensor, ads1x15.Pin.A2, ads1x15.Pin.A3)

        except (NameError, ValueError, OSError, AttributeError, TypeError) as e:
            print(f"[{self.name}] Hardware failure: {e}")
            
            if hasattr(self, 'i2c') and self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass
            return  

        self.initialized = True

    def get_params(self, num):

        if num == 'HCl_B1': 
            self.params.append({
                "shunt_ohms": 220.0,
                "maximum_ppm": 100,
                "minimum_ppm": 0,
                "min_current_ma": 4.0,
                "max_current_ma": 20.0,
            })

        elif num == 'IRC-A1':
            self.params.append({
                "shunt_ohms": 220.0,
                "maximum_ppm": 5000,
                "minimum_ppm": 0,
                "min_current_ma": 4.0,
                "max_current_ma": 20.0,
            })

        else:
            print('Issue with serial_num')
    
    def process(self):

        try:
            # Measure voltage
            mvolt0, timestamp0 = self.measure_mv(self,self.chan0)
            mvolt1, timestamp1 = self.measure_mv(self,self.chan1)

            # Calculate concentration from voltage
            conc0 = self.calc_conc(mvolt0,self.serial_num[0])
            conc1 = self.calc_conc(mvolt1,self.serial_num[1])

            # Emit data in slot
            self.emit_data(mvolt0,'CO2',conc0,timestamp0)
            self.emit_data(mvolt1,'HCl',conc1,timestamp1)

        except Exception as e:
            self._safe_shutdown(reason = e)

    def measure_mv(self,channel):

        # Clean ADC memory for more accurate second read
        _ = channel.voltage()
        time.sleep(0.01)

        # Perform voltage reading
        mvolt = channel.voltage * 1000

        # Timestamp returning result
        timestamp = self.timestamp()
        time.sleep(0.01)

        return(mvolt,timestamp)

    def calc_conc(self,v_diff,identity):
        self.get_params(identity)

        current_ma = (v_diff / self.params.shunt_ohms) * 1000.0

        if identity == "HCl-B1":
            conc = (current_ma*(self.params["maximum_ppm"]-self.params["minimum_ppm"]))/(self.params["max_current_ma"]-self.params["min_current_ma"]) #want to switch these with the maximum and minimum ppm for calibration so it can be easily adjsuted
        elif identity == "IRC-A1":
            conc = (current_ma*(self.params["maximum_ppm"]-self.params["minimum_ppm"]))/(self.params["max_current_ma"]-self.params["min_current_ma"])
        else:
            raise ValueError(f"Unknown sensor type: {identity}")
        
        return conc

    def emit_data(self,identity,mvolt,conc,timestamp):
        # Your specific sensor logic here
        data = {'mvolt': mvolt,
                'name' : identity,
                'conc' : conc,
                'timestamp' : timestamp}
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