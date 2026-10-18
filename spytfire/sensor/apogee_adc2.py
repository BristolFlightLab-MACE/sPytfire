# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 11:29:30 2026

This module codes the operation of the Apogee SL-510 and SL-610 thermopile 
pygeometers and SP-510 and SP-610 pyronometers

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================
from dataclasses import dataclass, asdict

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Signal, QObject

# Import numpy for calculating the longwave and shortwave results from the 
# apogee sensors
import numpy as np

import time

from adafruit_ads1x15 import ADS1115, AnalogIn, ads1x15
import smbus2

from spytfire.base import BaseWorker

@dataclass(frozen=True)
class ApogeeLSample:
    """A simple container for a single Apogee longwave sample."""
    voltage0: float
    voltage1: float
    sensor_t: float
    radiative_flux: float
    excite_v: float
    timestamp: int

@dataclass(frozen=True)
class ApogeeSSample:
    """A simple container for a single Apogee shortwave sample."""
    voltage: float
    radiative_flux: float
    timestamp: int

@dataclass(frozen=True)
class VoltageSample:
    """A simple container for a single voltage sample."""
    voltage_v: float
    timestamp_ns: int

class ADCMeasurementManager(BaseWorker):
    data_ready = Signal(str, str, dict)

    def __init__(self,name, serial_num = None, address = None, interval_ms = None)
    def __init__(self,i2cbus,address_8channel,address_2channel):
        super().__init__()

        # Setup 8 channel adc
        self.bus = i2cbus
        _, i2caddress = address_8channel
        self.I2C_ADDR = i2caddress

        self.channel_hex={
            'SELECT_CH0_CH1'  :0xA0,
            'SELECT_CH2_CH3'  :0xA1,
            'SELECT_CH4_CH5'  :0xA2,
            'SELECT_CH6_CH7'  :0xA3,
            'SELECT_CH8_CH9'  :0xA4,
            'SELECT_CH10_CH11':0xA5,
            'SELECT_CH12_CH13':0xA6,
            'SELECT_CH14_CH15':0xA7
        }

        self.vref = 3.3                 # REF+ driven from the Pi's 3.3V rail, REF- to GND

        self.CONVERSION_DELAY_S = 0.17  # datasheet worst case ~150ms, padded

        # Setup 2 channel adc
        _ , i2caddress = address_2channel
        self.ads = ADS1115(i2cbus, address=i2caddress)
        self.chan0 = AnalogIn(self.ads, ads1x15.Pin.A0, ads1x15.Pin.A1)
        self.chan1 = AnalogIn(self.ads, ads1x15.Pin.A0, ads1x15.Pin.A1)

        self.initialized = True

    def start_work(self):
        while self.initialized:
            self.vref = self.measure_voltage(channel = 0)
            timestamp = self.timestamp()
            self.data_ready.emit()

            self.ap_vcc = self.measure_voltage(channel = 1)
            self.timestamp()
            self.data_ready.emit()

            voltage0 = self.read_diff_channel(self,'SELECT_CH0_CH1')
            voltage1 = self.read_diff_channel(self,'SELECT_CH2_CH3')
            timestamp = self.timestamp()
            self.data_ready.emit()

            self.vref = self.measure_voltage(channel = 0)
            timestamp = self.timestamp()
            self.data_ready.emit()

            self.ap_vcc = self.measure_voltage(channel = 1)
            timestamp = self.timestamp()
            self.data_ready.emit()

            voltage0 = self.read_diff_channel(self,'SELECT_CH4_CH5')
            voltage1 = self.read_diff_channel(self,'SELECT_CH6_CH7')
            timestamp = self.timestamp()
            self.data_ready.emit()

            self.vref = self.measure_voltage(channel = 0)
            timestamp = self.timestamp()
            self.data_ready.emit()

            voltage0 = self.read_diff_channel(self,'SELECT_CH8_CH9')
            voltage1 = self.read_diff_channel(self,'SELECT_CH10_CH11')
            timestamp = self.timestamp()
            self.data_ready.emit()

    def measure_voltage(self,channel = 0):
        if channel == 0:
            _ = self.chan0.voltage      # throw away stale conversion
            time.sleep(0.01)
            return self.chan0.voltage
        elif channel == 1:
            _ = self.chan1.voltage      # throw away stale conversion
            time.sleep(0.01)
            return self.chan1.voltage
        else:
            return None

    def read_diff_channel(self,channel_select):
        # Select the channel, then wait for the conversion to finish
        self.bus.write_byte(self.I2C_ADDR, self.channel_hex[channel_select])
        time.sleep(self.CONVERSION_DELAY_S)

        # Read back the 32-bit result
        msg = smbus2.i2c_msg.read(self.I2C_ADDR, 4)
        self.bus.i2c_rdwr(msg)
        b0, b1, b2, b3 = list(msg)

        raw32 = (b0 << 24) | (b1 << 16) | (b2 << 8) | b3
        sign_bits = (raw32 >> 30) & 0b11
        adc_code = (raw32 >> 6) & 0xFFFFFF

        match sign_bits:
            case 0b00:
                print("underrange (input below -FS)")
            case 0b11:
                print("overrange (input above +FS)")
            case 0b10:  # positive
                return 0.5 * self.vref * (adc_code / 16777215.0)
            case 0b01:  # negative
                return -0.5 * self.vref * ((16777216 - adc_code) / 16777215.0)
            case _:
                print("sign error")

@Slot(str, str, dict)
class ApogeeSensorWorker2(BaseWorker):
    data_ready = Signal(str, str, dict)

    def __init__(self,i2cbus,address_8channel,address_2channel):
        ADCMeasurementManager

    def find_coefficients(serial_num):
        coeff_dict = {}
        coeff_dict['SL510_1729'] = [8.410, 1.023]
        coeff_dict['SL610_1463'] = [8.610, 1.029]
        coeff_dict['SP510_3985'] = [22.78]
        coeff_dict['SP610_1707'] = [28.99]

        try:
            k = coeff_dict[serial_num]
        except KeyError:
            k = None
            print(f'Unknown apogee instrument {serial_num}')

        return k

    def calc_longwave(self, k, voltage0, voltage1, excitation):

        # Extract calibration coefficients
        k1,k2 = k

        # Calculate temperature
        Rt = 24900*(voltage1/(excitation-voltage1))
        
        # Steinhart-Hart equation coefficients (above and below O doesn't change
        # the outcome much!)
        
        # Coefficients for positive temperature for thermistor
        A = 9.32794E-4
        B = 2.21451E-4
        C = 1.26233E-7
        
        Tk = np.divide(1, A + B * np.log(Rt) + C * np.power(np.log(Rt),3))

        '''
        if Tk < 273.15:
            A = 9.32960E-4
            B = 2.21424E-4
            C = 1.26329E-7
            
            Tk = np.divide(1, A + B * np.log(Rt) + C * np.power(np.log(Rt),3))
        '''
        
        boltz = 5.6704E-8 #W m-2 K-4
        
        LW = k1*voltage0*1000 + k2*boltz*np.power(Tk,4)
        
        return Tk,LW

    def calc_shortwave(self,k,voltage0):
            
        sw = k * voltage0 * 1000
            
        return sw