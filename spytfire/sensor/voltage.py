# -*- coding: utf-8 -*-
"""
Created on Fri Apr 17 13:45:04 2026

This module codes the operation of the voltage sensor for the analogue apogee
sensors. It's structure is very similar to the analogue apogee sensor structure

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================

from dataclasses import dataclass, asdict

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BasePollingWorker

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal

from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15

# =============================================================================

@dataclass(frozen=True)
class VoltageSample:
    """A simple container for a single voltage sample."""
    excite_V: float
    timestamp_ns: int

class VoltageSensorWorker(BasePollingWorker):
    '''Class to read the excitation voltage from the ADC and emit it to the controller.'''
    data_ready = Signal(str, str, dict)

    def __init__(self, name, serial_num=None, address=None, interval_ms=200, i2cbus=None):
        """
        A BasePollingWorker that uses an Adafruit ADS1115 to measure the
        differential voltage placed across the Apogee longwave sensors.

        Parameters
        ----------
        name : string
            Unique identifier for the sensor instance.
        serial_num : string, optional
            Device serial number, if available. Not used by this sensor.
        address : tuple
            (mux_channel, i2c_address) for the ADS1115.
        interval_ms : int, optional
            Polling interval between measurements, in milliseconds.
        i2cbus : object, optional
            The multiplexer bus object that exposes the per-channel I2C bus.

        Emits
        ----------
        data_ready : dict
            A dictionary containing the measurement in volts and the acquisition
            timestamp from the local monotonic clock.
        """
        super().__init__(name=name, serial_num=serial_num, address=address, interval_ms=interval_ms)

        self.ads = None
        self.chan0 = None
        self.model = name
        self.initialized = False

        try:
            _ , i2caddress = address
            self.ads = ADS1115(i2cbus, address=i2caddress)
            self.chan0 = AnalogIn(self.ads, ads1x15.Pin.A0, ads1x15.Pin.A1)
            self.initialized = True

        except (NameError, ValueError, OSError, AttributeError, TypeError) as exc:
            print(f"[{name}] Hardware failure: {exc}")
            self.ads = None
            self.chan0 = None
            self.initialized = False

    def process(self):
        if not self.initialized or self.chan0 is None:
            return

        try:
            sample = VoltageSample(
                excite_V=float(self.chan0.voltage),
                timestamp_ns=self.timestamp(),
            )

            self.data_ready.emit(self.name, 'voltage', asdict(sample))

        except Exception as exc:
            print(f"Voltage Read Error: {exc}")

        self.initialized = False