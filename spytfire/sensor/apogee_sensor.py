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

def find_coefficients(serial_num):

    # SL-510-SS_1729 coefficients
    if serial_num == 'SL510_1729':
        k1 = 8.410 #W m-2 mV-1
        k2 = 1.023 #Unitless
        k = [k1, k2]

    # SL-610-SS_1463 coefficients
    elif serial_num == 'SL610_1463':
        k1 = 8.610 #W m-2 mV-1
        k2 = 1.029 #Unitless
        k = [k1, k2]

    # Calibration constant of SP-510-SS 3985
    elif serial_num == 'SP510_3985':
        k = 22.78

    # Calibration constant of SP-610-SS 1707
    elif serial_num == 'SP610_1707':
        k = 28.99

    else:
        print(f'Unknown apogee instrument {serial_num}')


    return k

def calc_longwave(k, voltage0, voltage1, excitation):

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

def calc_shortwave(k, voltage0):
        
    sw = k * voltage0 * 1000
        
    return sw

# =============================================================================
# Define the worker to monitor Apogee Sensors through an ADS1115
# =============================================================================

class ApogeeSensorWorker(BasePollingWorker):
    '''Class to read an ADS1115 and interpret the voltages as Apogee signals.'''
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num, interval_ms=200):

        """
        A BasePollingWorker to connect and operate either 1 or 2
        components of the Apogee net 4 part net radiometer made from
        analogue Apogee pyronometers and pyrgeometers.

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use
        serial_num : string
            The specific apogee instrument in use (needed to retrieve
            calibration coefficients)
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

        self.serial_num = serial_num

        try:
            # Create the I2C bus
            i2c = board.I2C()
            
            match self.name:
                case 'Pygeo_Up':
                    address = 75  # SCL
                    
                case 'Pygeo_Down':
                    address = 72  # GND
                    
                case 'Pyronometer':
                    address = 73  # VIN
                    
                case _:
                    raise ValueError('apogee sensor not yet supported')  
            
            # Create the ADC object using the I2C bus
            self.sensor = ADS1115(i2c,address = address)
            
        except (NameError, ValueError, OSError, AttributeError) as e:
            print(f"[{self.name}] Hardware failure: {e}")
            
            if hasattr(self, 'i2c') and self.i2c:
                try:
                    self.i2c.deinit()
                except:
                    pass
            return

        if address == 75 or address == 72:
            # Create differential input between channel 0 and 1
            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0, ads1x15.Pin.A1)
            
            # Create differential input between channel 2 and 3
            self.chan1 = AnalogIn(self.sensor, ads1x15.Pin.A2, ads1x15.Pin.A3)
            
        elif address == 73 and type(self.serial_num) == list:
            # Create differential input between channel 0 and 1
            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0, ads1x15.Pin.A1)
            
            # Create differential input between channel 2 and 3
            self.chan1 = AnalogIn(self.sensor, ads1x15.Pin.A2, ads1x15.Pin.A3)

        elif address == 73:
            # Create single differential input between channel 0 and 1
            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0, ads1x15.Pin.A1)

        self.initialized = True
    
    def process(self):
        try:
            if self.name == "Pygeo_Up" or self.name == "Pygeo_Down":
                
                v0, v1 = self.chan0.voltage,self.chan1.voltage
                
                excitation_v = 3.2827
                
                k = find_coefficients(self.serial_num)

                # Move calculation to main
                temp,longwave = calc_longwave(k, v0, v1, excitation_v)
                
                temp = temp - 273.15

                if self.name == 'Pygeo_Up':
                    sensor_type = 'apogee_lu'
                else:
                    sensor_type = 'apogee_ld'
                
                apogee_dict = {'voltage0': v0,
                               'voltage1': v1,
                               'sensor_t': temp,
                               'radiative_flux': longwave,
                               'excite_v': excitation_v,
                               'timestamp': self.timestamp()
                              }
                
                self.data_ready.emit(self.name, sensor_type, apogee_dict)
            
            elif self.name == 'Pyronometer' and type(self.serial_num) == list:
                
                _ = self.chan0.voltage      # throw away stale conversion
                time.sleep(0.01)
                v0 = self.chan0.voltage
                
                # Read channel 1
                _ = self.chan1.voltage
                time.sleep(0.01)
                v1 = self.chan1.voltage

                k0 = find_coefficients(self.serial_num[0])
                k1 = find_coefficients(self.serial_num[1])

                shortwave0 = calc_shortwave(k0, v0)
                shortwave1 = calc_shortwave(k1, v1)
                
                timestamp = self.timestamp()

                apogee_dict = {'voltage': v0,
                               'radiative_flux': shortwave0,
                               'timestamp': timestamp
                              }
                self.data_ready.emit(self.name, 'apogee_su', apogee_dict)

                apogee_dict = {'voltage': v1,
                               'radiative_flux': shortwave1,
                               'timestamp': timestamp
                              }
                self.data_ready.emit(self.name, 'apogee_sd', apogee_dict)
            
        except Exception as e:
            print(f"Apogee Read Error: {e}")

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