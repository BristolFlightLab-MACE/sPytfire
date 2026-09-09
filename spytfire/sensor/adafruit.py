# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 12:56:52 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)
"""
# =============================================================================

from dataclasses import dataclass, asdict

# Import the BasePolling Worker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

from adafruit_as7341 import AS7341, Gain

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

import time

@dataclass(frozen=True)
class AdafruitSample:
    """A simple container for a single simple spectral sample."""
    channel_415: int
    channel_445: int
    channel_480: int   
    channel_515: int
    channel_555: int
    channel_590: int
    channel_630: int
    channel_680: int
    channel_nir: int
    channel_clr: int
    exposure_t: float
    timestamp_ns: int

# =============================================================================

class AdafruitSensorWorker(BasePollingWorker):
    '''Class to read an Adafruit AS7341 10-channel spectrometer.'''
    data_ready = Signal(str, str, dict)

    def __init__(self, name, serial_num = None, address = None, interval_ms=1000, i2cbus=None):
        """
        Connect to and operate an Adafruit AS7341 10-channel spectrometer.

        Parameters
        ----------
        name : string
            Unique identifier for the sensor instance.
        serial_num : string, optional
            Device serial number, if available. Not used by this sensor.
        address : tuple, optional
            ``(mux_channel, i2c_address)`` for the AS7341.
        interval_ms : int, optional
            Polling interval between measurements, in milliseconds.
        i2cbus : object, optional
            I2C multiplexer exposing the selected channel.

        Attributes
        ----------
        sensor : 
            The Adafruit AS7341 I2C connection is held by this attribute
        is_initialized : bool
            Value that can be read outside the class to monitor the connection

        Emits
        ----------
        data_ready : dict
            Channel readings, exposure time, and acquisition timestamp.

        """
        # Pass shared variables to BasePollingWorker
        super().__init__(name, serial_num, address, interval_ms)

        try:
            self.sensor = AS7341(i2cbus)
            
            self.sensor.gain = Gain.GAIN_0_5X
            
            # Starting default for adafruit sensor is atime = 100 and astep = 999
            #self.atime = self.sensor.atime
            #self.astep = self.sensor.astep
            
            # Set predefined exposure times
            self.astep_table = [59, 119, 299, 599, 1198, 2997, 5994, 11989, 29975, 53956]
            # gives exposure times of [1, 2, 5, 10, 20, 50, 100, 200, 500, 900] ms to within 0.1%
            self.exposure_index = 6  # start at 100 ms
            
            # Set default starting parameters independant of sensor object
            self.atime = 5  #In this example is fixed
            self.astep = self.astep_table[self.exposure_index]
            self.sensor.atime = self.atime
            self.sensor.astep = self.astep
            self.needs_cooldown = False

            # Exposure time in µs
            self.exposure_time = (self.atime + 1) * (self.astep + 1) * 2.78

            self.sensor.led_current = 50

            self.flash_LED(repeats = 2)
            
            self.initialized = True
            
        except (NameError, ValueError, OSError, AttributeError, TypeError, RuntimeError) as exc:
            print(f"[{name}] Hardware failure: {exc}")
            self.sensor = None
            return
    
    def flash_LED(self, repeats = 1):
            loops = 0
            while loops < repeats:
                self.sensor.led = True
                time.sleep(0.1)
                self.sensor.led = False
                time.sleep(0.1)
                loops += 1
            return
    
    def autoscale_integration(self, readings_list):

        # Test at low light levels to see if the current code still operates
        # with the smaller dynamic range expected at low light levels.

        peak = max(readings_list)
        changed = False
    
        current_limit = min(65535, (self.atime + 1) * (self.astep + 1))
        min_limit = current_limit * 0.30
        max_limit = current_limit * 0.85
        warn_limit = current_limit * 0.99
        
        if peak > warn_limit and self.exposure_index > 2:
            self.exposure_index -= 3
            changed = True
            
        elif peak > max_limit and self.exposure_index > 0:
            self.exposure_index -= 1
            changed = True

        elif peak < min_limit and self.exposure_index < len(self.astep_table) - 1:
            self.exposure_index += 1
            changed = True
    
        if changed:
            self.astep = self.astep_table[self.exposure_index]
            self.sensor.astep = self.astep
            self.exposure_time = (self.atime + 1) * (self.astep + 1) * 2.78
            self.needs_cooldown = True
    
        return
    
    def autoscale_integration_old(self,readings_list):
        peak = max(readings_list)
        changed = False
        
        # Calculate the hardware-defined ceiling
        # Reference: ams OSRAM AS7341 Datasheet (Max counts calculation)
        current_limit = min(65535,((self.atime + 1) * (self.astep + 1)))
        
        # SITUATION 1: HARD CLIPPING
        # If peak is at or very near the limit, we are blind to higher intensities.
        if peak >= (current_limit - 1):
            if self.atime > 10:
                self.atime = max(0, self.atime - 10)
                self.sensor.atime = self.atime
                changed = True
                #print(f"CLIPPED at {peak}! Reducing ATIME to {self.sensor.atime}")

            elif self.astep > 100:
                self.astep -= 100
                self.sensor.astep = self.astep
                changed = True
                #print(f"CLIPPED at min ATIME! Reducing ASTEP to {self.sensor.astep}")
    
        # SITUATION 2: HIGH SIGNAL (PREVENTATIVE)
        elif peak > (current_limit * 0.85) and self.atime > 0:
            self.atime = max(0, self.atime - 2)
            self.sensor.atime = self.atime
            changed = True
            #print(f"Saturation risk! ATIME decreased to {self.sensor.atime}")
    
        # SITUATION 3: LOW SIGNAL
        elif peak < (current_limit * 0.15):
            if self.atime < 255:
                self.atime = min(255, self.atime + 5)
                self.sensor.atime = self.atime
                changed = True
            elif self.astep < 899:
                self.astep += 100
                self.sensor.astep = self.astep
                changed = True
                #print(f"Signal weak. ATIME increased to {self.sensor.atime}")

        if changed:
            self.exposure_time = (self.atime + 1) * (self.astep + 1)*2.78
            self.needs_cooldown = True
        return
    
    def process(self):
        try:
            if self.needs_cooldown:
                _ = self.sensor.all_channels 
                self.needs_cooldown = False
                return # Exit and wait for the next interval for clean data
            
            raw_vals = self.sensor.all_channels
            ir = self.sensor.channel_nir
            clr = self.sensor.channel_clear
            
            data = list(raw_vals) + [ir,clr]

            sample = AdafruitSample(
                channel_415=data[0],
                channel_445=data[1],
                channel_480=data[2],
                channel_515=data[3],
                channel_555=data[4],
                channel_590=data[5],
                channel_630=data[6],
                channel_680=data[7],
                channel_nir=data[8],
                channel_clr=data[9],
                exposure_t=self.exposure_time,
                timestamp_ns=self.timestamp()
            )
            
            self.data_ready.emit(self.name, 'ada_as7341', asdict(sample))
            self.autoscale_integration(data)
            
            self.flash_LED()
    
        except Exception as exc:
            print(f"Adafruit Read Error: {exc}")

    def _safe_shutdown(self,reason="Unknown Error"):   
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")

        self.sensor.led = False
        self.initialized = False