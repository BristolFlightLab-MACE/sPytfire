# -*- coding: utf-8 -*-
"""
Created on Tue May 26 20:22:47 2026

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

# Key imports for running alphasense OPC using USB interface
from usbiss.spi import SPI

try:
    # This module is needed if running alphasense OPC using SPI interface
    import spidev
except ModuleNotFoundError:
    print("spidev not found: Install if on Linux")

# Libary for operating alphasense OPC
import opcng as opc

import time

# =============================================================================

class OPCSensorWorker(BasePollingWorker):
    '''Class to read the alphasense OPC-N3 and emit it to the controller.'''
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, address = None, interval_ms=200, i2cbus=None):
        """
        Connect to and operate an Alphasense OPC-N3 optical particle counter.

        Parameters
        ----------
        name : string
            Unique identifier for the sensor instance.
        serial_num : string, optional
            Device serial number, if available. Not used by this sensor.
        address : object, optional
            Device interface address, if applicable.
        interval_ms : int, optional
            Polling interval between measurements, in milliseconds.
        i2cbus : object, optional
            Accepted for the shared worker interface; OPC-N3 uses SPI or USB.

        Attributes
        ----------
        sensor : 
            The OPC-N3 connection is held by this attribute
        is_initialized : bool
            Value that can be read outside the class to monitor the connection
        
        Emits
        ----------
        data_ready : dict
            OPC status, particle-size bins, PM2.5, PM10, and timestamp.

        """   
        
        # Pass shared variables to BasePollingWorker
        super().__init__(name, serial_num, address, interval_ms)
        
        # Initialise as None to let code check for connection
        spi = None

        # First, try spi connection
        try:
            spi = spidev.SpiDev()
            spi.open(0, 0)
        except Exception as exc:
            print(f"[{name}] OPC SPI setup failed: {exc}")
            self.initialized = False
            self.sensor = None
            return

        if spi is None:
            try:
                # Two options depending on whether usb or spi connection is used
                #spi = SPI('/dev/ttyACM0')
                spi = SPI('COM3')

            except Exception as exc:
                print(f"[{name}] OPC USB setup failed: {exc}")
                self.initialized = False
                self.sensor = None
                return

        # Return to common code
        spi.mode = 1
        #spi.max_speed_hz = 500000
        spi.max_speed_hz = 250000
        spi.lsbfirst = False
        self.spi = spi

        try:
            self.sensor = opc.detect(spi)
            self.sensor.on()
        except Exception as exc:
            print(f"[{name}] OPC USB setup failed: {exc}")
            self.initialized = False
            self.sensor = None
            return
            
        # Track hardware error states
        self.consecutive_failures = 0
        self.MAX_ALLOWED_FAILURES = 5  # Shut down after ~5 failed attempts
        
        time.sleep(0.6)                # Recommended 600 ms before measurements

        # Probe once so a missing/quiet sensor is detected immediately.
        self.sensor.histogram()
        
        self.initialized = True
    
    def process(self):
        try:                
            values = self.sensor.histogram()
            
            # Create full list of parameters
            channels = {f'bin{i}': values[f'Bin {i}'] for i in range(24)}
            channels.update({f'bin{i}mtof': values[f'Bin{i} MToF'] for i in [1, 3, 5, 7]})
            channels['sampling_period'] = values['Sampling Period']
            channels['temperature'] = values['Temperature']
            channels['rh'] = values['Relative humidity']
            channels['pm1']   = values['PM1']
            channels['pm2.5'] = values['PM2.5']
            channels['pm10']  = values['PM10']
            channels['sfr']   = values['SFR']
            channels['laser_status'] = values['Laser status']
            channels['timestamp_ns'] = self.timestamp()
            
            self.data_ready.emit(self.name, 'alpha_opc', channels)
            self.consecutive_failures = 0
        
        except (KeyError, ValueError) as data_err:
            # Catch bad dictionary mapping structures or corrupt byte conversions
            self.consecutive_failures += 1
            print(f"[{self.name}] Corrupt data stream format (Error {self.consecutive_failures}/{self.MAX_ALLOWED_FAILURES}): {data_err}")
     
            if self.consecutive_failures >= self.MAX_ALLOWED_FAILURES:
                self._safe_shutdown(reason="Repeated Data Corruption/Key Errors")
        
        except Exception as hardware_err:
            self.consecutive_failures += 1
            print(f"[{self.name}] OPC read failed ({self.consecutive_failures}/{self.MAX_ALLOWED_FAILURES}): {hardware_err}")
            
            if self.consecutive_failures >= self.MAX_ALLOWED_FAILURES:
                self._safe_shutdown(reason="Repeated OPC read failures")
    
                
    def _safe_shutdown(self, reason="Unknown Error"):
        """
        Gracefully de-energizes the sensor peripherals to prevent damage.
        """
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")
        
        if hasattr(self, 'sensor') and self.sensor is not None:
            try:
                # Disables both the internal 658nm laser and the sample fan safely
                self.sensor.off()
                print(f"[{self.name}] Laser and Fan powered down successfully.")
                self.spi.close()
            except Exception as shutdown_err:
                print(f"[{self.name}] Hard hardware control failed: {shutdown_err}")
        else:
            print(f"[{self.name}] Cannot disable hardware: Connection reference is missing")
            
        self.initialized = False