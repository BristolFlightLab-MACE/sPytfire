# -*- coding: utf-8 -*-
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

def calc_longwave(model, voltage0, voltage1, excitation):
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
    
    # SL-510-SS_1729 coefficients
    if model == 'SL510_1729':
        k1 = 8.410 #W m-2 mV-1
        k2 = 1.023 #Unitless
        
    # SL-610-SS_1463 coefficients        
    elif model == 'SL610_1463':
        k1 = 8.610 #W m-2 mV-1
        k2 = 1.029 #Unitless
    
    boltz = 5.6704E-8 #W m-2 K-4
    
    LW = k1*voltage0*1000 + k2*boltz*np.power(Tk,4)
    
    return Tk,LW

def calc_shortwave(name, voltage0):
    
    # Calibration constant of SP-510-SS 3985
    if name == 'SP510_3985':
        k = 22.78
    
    # Calibration constant of SP-610-SS 1707
    if name == 'SP610_1707':
        k = 28.99
    
    sw = k * voltage0 * 1000
        
    return sw

# =============================================================================
# Define the worker to monitor Apogee Sensors through an ADS1115
# =============================================================================

class ApogeeSensorWorker(BasePollingWorker):
    '''Class to read an ADS1115 and interpret the voltages as Apogee signals.'''
    data_ready = Signal(str, dict)
    
    def __init__(self, name, interval_ms=200):

        """
        A BasePollingWorker to connect and operate either 1 or 2
        components of the Apogee net 4 part net radiometer made from
        analogue Apogee pyronometers and pyrgeometers.

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use
        interval_ms : int, optional (Default is 200 ms)
            Provided the repolling time between each measurement start

        Attributes
        ----------
        sensor : 
            The Adafruit ADS1115 I2C connection is held by this attribute
        is_initialized : bool
            Value that can be read outside the class to monitor the connection

        Emits
        ----------
        data_ready : dictionary
            A dictionary object containing information on the two
            analogue channels on the ADS1115 board that can measure the
            internal temperature of pyrgeometer and the incoming radiation
            (either shortwave or longwave depending on the instrument).
            For pyronometers, 2x instruments should be connected to the
            same ADS1115
        """
        
        # Pass shared variables to BaseWorker
        super().__init__(name, interval_ms)
        
        try:
            # Create the I2C bus
            i2c = board.I2C()
            
            match name:
                case 'SL510_1729':
                    address = 75  # SCL
                    
                case 'SL610_1463':
                    address = 72  # GND
                    
                case 'SP510_3985':
                    address = 73  # VIN
                    
                case 'SP610_1707':
                    address = 73  # VIN
                    
                case _:
                    raise ValueError('apogee sensor not yet supported')  
            
            # Create the ADC object using the I2C bus
            self.sensor = ADS1115(i2c,address = address)
            
        except (NameError, ValueError, OSError, AttributeError) as e:
            print(f"[{name}] Hardware failure: {e}")
            
            # CLEANUP: If the bus was created but sensor failed, release the bus
            if hasattr(self, 'i2c') and self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass 
            self.sensor = None
            return
                
        if name == "SL510_1729" or name == "SL610_1463":
            # Create differential input between channel 0 and 1
            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0, ads1x15.Pin.A1)
            
            # Create differential input between channel 2 and 3
            self.chan1 = AnalogIn(self.sensor, ads1x15.Pin.A2, ads1x15.Pin.A3)
            
        elif name =='SP510_3985' or name =='SP610_1707':
            # Create differential input between channel 0 and 1
            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0, ads1x15.Pin.A1)
            
            # Create differential input between channel 2 and 3
            self.chan1 = AnalogIn(self.sensor, ads1x15.Pin.A2, ads1x15.Pin.A3)
        
        # Isolate the name of the device so that the calibration coefficents
        # can be used
        self.model = name
        
        self.initialized = True
    
    def process(self):
        try:
            if self.model == "SL510_1729" or self.model == "SL610_1463":
                v0, v1 = self.chan0.voltage,self.chan1.voltage
                
                excitation_v = 3.2827
                
                # Move calculation to main
                temp,longwave = calc_longwave(self.model, v0, v1, excitation_v)
                
                temp = temp - 273.15
                
                apogee_dict = {'voltage0': v0,
                               'voltage1': v1,
                               'sensor_t': temp,
                               'radiative_flux': longwave,
                               'excite_v': excitation_v,
                               'timestamp': self.timestamp()
                              }
            
            elif self.model == 'SP510_3985' or self.model == 'SP610_1707':
                
                _ = self.chan0.voltage      # throw away stale conversion
                time.sleep(0.01)
                v0 = self.chan0.voltage
                
                # Read channel 1
                _ = self.chan1.voltage
                time.sleep(0.01)
                v1 = self.chan1.voltage
                
                shortwave0 = calc_shortwave('SP510_3985', v0)
                shortwave1 = calc_shortwave('SP610_1707', v1)
                
                apogee_dict = {'voltage0': v0,
                               'radiative_flux0': shortwave0,
                               'voltage1': v1,
                               'radiative_flux1': shortwave1,
                               'timestamp': self.timestamp()
                              }
            self.data_ready.emit(self.model, apogee_dict)
            
        except Exception as e:
            print(f"Apogee Read Error: {e}")