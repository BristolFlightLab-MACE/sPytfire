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
from spytfire.sensor.apogee import find_coefficients

###############################################################################


###############################################################################
# =============================================================================

class sensor_params():
    def __init__(self,serial_num,sensor_type):
        self.serial_num = serial_num
        match sensor_type:
            # Suggested algorithm -> H2SA 2, NO2A 1, OXA 3, SO2A 4
            # Backup algorithm    -> H2SA 1, NO2A 3, OXA 1, SO2A 1/3
            case 'alpha_no2':
                self.algorithm = 1
                match self.serial_num:
                    case 212500902:
                        self.sensitivity0 = 0.250
                        self.sensitivity1 = None

                        self.WEe,self.AEe,self.WE0,self.AE0 = [292,295,2,0]
                    case _:
                        raise KeyError(f'Serial num {self.serial_num} unknown for sensor_type: {sensor_type}')
                    
            case 'alpha_o3':
                self.algorithm = 3
                match self.serial_num:
                    case 214880557:
                        self.sensitivity0 = 0.240
                        self.sensitivity1 = 0.402

                        self.WEe,self.AEe,self.WE0,self.AE0 = [398,420,5,0]

                        self.no2_coefficients = sensor_params(212500902,'alpha_no2')
                    case _:
                        raise KeyError(f'Serial num {self.serial_num} unknown for sensor_type: {sensor_type}')
                    
            case 'alpha_h2s':
                self.algorithm = 2
                match self.serial_num:
                    case 133590062:
                        self.sensitivity0 = 1.409
                        self.sensitivity1 = None

                        self.WEe,self.AEe,self.WE0,self.AE0 = [285,287,14,9]
                    case _:
                        raise KeyError(f'Serial num {self.serial_num} unknown for sensor_type: {sensor_type}')
                    
            case 'alpha_so2':
                self.algorithm = 4
                match self.serial_num:
                    case 134880636:
                        self.sensitivity0 = 0.281
                        self.sensitivity1 = None
                        self.WEe,self.AEe,self.WE0,self.AE0 = [284,283,-4,0]
                    
                    case _:
                        raise KeyError(f'Serial num {self.serial_num} unknown for sensor_type: {sensor_type}')
            case _:
                raise KeyError(f'No gas algorithm of sensor_type: {sensor_type}')

def calc_WEc(sensor,coefficients,sensor_type=None):
    # See alphasense application note AAN 803-05 for details of the algorithm and lookup tables
    TEMPERATURE_LOOKUP = np.arange(-30,55,10)

    H2S_LOOKUP = {1: [ 3  , 3  , 3  , 1  ,-1  ,-2  ,-1.5, -1  , -0.5],
                  2: [-1.5,-1.5,-1.5,-0.5, 0.5, 1  , 0.8,  0.5,  0.3],
                  3: [ 9  , 9  , 9  , 9  , 3  , 1  , 0.3,  0.3,  0.3],
                  4: [50  ,46  ,43  ,37  ,25  , 0  ,-8  ,-16  ,-20  ]
                  }

    NO2_LOOKUP = {1: [ 0.8, 0.8, 1  , 1.2, 1.6, 1.8, 1.9,  2.5,  3.6],
                  2: [ 0.4, 0.4, 0.6, 0.7, 0.9, 1  , 1.1,  1.4,  2  ],
                  3: [ 0.2, 0.2, 0.2, 0.2, 0.7, 1  , 1.3,  2.1,  3.5],
                  4: [-4  ,-4  ,-4  ,-4  ,-2  , 0  ,10  , 35  ,132  ]
                  }

    OX_LOOKUP  = {1: [ 1  , 1.2, 1.2, 1.6, 1.7, 2  , 2.1,  3.4,  4.6],
                  2: [ 0.5, 0.6, 0.6, 0.8, 0.9, 1  , 1.1,  1.7,  2.3],
                  3: [ 0.1, 0.1, 0.2, 0.3, 0.7, 1  , 1.7,  3  ,  4  ],
                  4: [-5  ,-5  ,-4  ,-3  , 0.5, 0  , 9  , 42  ,134  ]
                  }

    SO2_LOOKUP = {1: [ 1.3, 1.3, 1.3, 1.2, 0.9, 0.4, 0.4,  0.4,  0.4],
                  2: [ 3.3, 3.3, 3.3, 3  , 2.3, 1  , 1  ,  1  ,  1  ],
                  3: [ 1.5, 1.5, 1.5, 1.5, 1  , 1  , 1  ,  1  ,  1  ],
                  4: [ 0  , 0  , 0  , 0  , 0  , 0  , 5  , 25  , 45  ]
                  }
    LOOKUPS = {'temp': TEMPERATURE_LOOKUP,
               'alpha_h2s' : H2S_LOOKUP,
               'alpha_no2' : NO2_LOOKUP,
               'alpha_o3'  : OX_LOOKUP,
               'alpha_so2' : SO2_LOOKUP
               }
    algorithm = coefficients.algorithm
    temperature_C = sensor.get('temperature_C')

    if temperature_C is None:
        temperature_C = 20

    if sensor_type in ['alpha_no2','alpha_h2s']:
        voltWEu_mV = sensor.get('mvolt0_mV')
        voltAEu_mV = sensor.get('mvolt1_mV')
    elif sensor_type in ['alpha_o3','alpha_so2']:
        voltWEu_mV = sensor.get('mvolt2_mV')
        voltAEu_mV = sensor.get('mvolt3_mV')

    voltWE_mV = voltWEu_mV - coefficients.WEe
    voltAE_mV = voltAEu_mV - coefficients.AEe
    
    lookup_T = LOOKUPS.get('temp')

    try:
        gas_l = LOOKUPS.get(sensor_type)[algorithm]
    except KeyError:
        print(f'Invalid gas {sensor_type} entered')
    
    if temperature_C < -30 or temperature_C > 50:
        temperature_C = 20
        print('Reset Temperature to 20 C')
    
    constant = np.interp(temperature_C,lookup_T,gas_l)
    
    match algorithm:
        case 1:
            voltWEc_mV = voltWE_mV - constant*voltAE_mV
        case 2:
            try:
                voltWEc_mV = voltWE_mV - constant*(coefficients.WE0/coefficients.AE0)*voltAE_mV
            except ZeroDivisionError:
                print('AE0 is 0')
                return 0
        case 3:
            voltWEc_mV = voltWE_mV - (coefficients.WE0-coefficients.AE0) - constant*voltAE_mV
        case 4:
            voltWEc_mV = voltWE_mV - coefficients.WE0 - constant
    return voltWEc_mV

def calc_concentration(sensor,sensor_type):

    sensor_coefficients = sensor_params(sensor['serial_num'],sensor_type)

    # OX sensor has a cross-sensitivity to NO2, so we need to calculate the NO2 concentration first
    if sensor_type == 'alpha_o3':
        no2WEc_mV = calc_WEc(sensor,
                             sensor_coefficients.no2_coefficients,
                             sensor_type = 'alpha_no2'
                             )
        
        no2_concentration_ppb = no2WEc_mV / sensor_coefficients.no2_coefficients.sensitivity0
        ox_WEc_no2_mv = no2_concentration_ppb * sensor_coefficients.sensitivity1

        # Correct the OX sensor's WEc voltage for the NO2 cross-sensitivity
        sensor['mvolt2_mV'] = sensor.get('mvolt2_mV') - ox_WEc_no2_mv
        voltWEc_mV = calc_WEc(sensor,
                              sensor_coefficients,
                              sensor_type = sensor_type,
                              )
    else:
        voltWEc_mV = calc_WEc(sensor,
                              sensor_coefficients,
                              sensor_type = sensor_type
                              )
    gas_conc_ppb = voltWEc_mV / sensor_coefficients.sensitivity0

    return gas_conc_ppb

@dataclass(frozen=True)
class GasSample4AFE:
    """A simple container for a single gas sensor sample."""
    mvolt0_mV: float
    mvolt1_mV: float
    mvolt2_mV: float
    mvolt3_mV: float
    name: str
    timestamp_ns: int
    serial_num: int

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

        self.serial_num = serial_num
        
        try:          
            _ , i2caddress = address

            # Create the ADC object using the I2C bus
            self.sensor = ADS1115(i2cbus, address = i2caddress)

            self.chan0 = AnalogIn(self.sensor, ads1x15.Pin.A0)
            self.chan1 = AnalogIn(self.sensor, ads1x15.Pin.A1)
            self.chan2 = AnalogIn(self.sensor, ads1x15.Pin.A2)
            self.chan3 = AnalogIn(self.sensor, ads1x15.Pin.A3)

            if self.name == 'NO2_O3':
                self.name0 = 'NO2'
                self.name1 = 'O3'
            elif self.name =='H2S_SO2':
                self.name0 = 'H2S'
                self.name1 = 'SO2'

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
        mvolt0 = self.measure_channel(self.chan0)
        mvolt1 = self.measure_channel(self.chan1)
        timestamp_samp0 = self.timestamp()
        mvolt2 = self.measure_channel(self.chan2)
        mvolt3 = self.measure_channel(self.chan3)
        timestamp_samp1 = self.timestamp()

        sample0 = GasSample4AFE(
            mvolt0_mV=mvolt0,
            mvolt1_mV=mvolt1,
            mvolt2_mV=0.0,
            mvolt3_mV=0.0,
            name=self.name0,
            timestamp_ns=timestamp_samp0,
            serial_num=self.serial_num[0]
            )

        if self.name == 'NO2_O3':
            sample1 = GasSample4AFE(
                mvolt0_mV=mvolt0,
                mvolt1_mV=mvolt1,
                mvolt2_mV=mvolt2,
                mvolt3_mV=mvolt3,
                name=self.name1,
                timestamp_ns=timestamp_samp1,
                serial_num=self.serial_num[1]
                )

        else:
            sample1 = GasSample4AFE(
                mvolt0_mV=0.0,
                mvolt1_mV=0.0,
                mvolt2_mV=mvolt2,
                mvolt3_mV=mvolt3,
                name=self.name1,
                timestamp_ns=timestamp_samp1,
                serial_num=self.serial_num[1]
            )

        self.data_ready.emit(self.name, 'alpha_' + self.name0.lower(), asdict(sample0))
        self.data_ready.emit(self.name, 'alpha_' + self.name1.lower(), asdict(sample1))
        
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