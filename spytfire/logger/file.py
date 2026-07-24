"""
Created on Tue Mar 31 12:04:52 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import QObject, Slot, Signal

import numpy as np
from pathlib import Path
import os

from spytfire.sensor.apogee import calc_longwave, find_coefficients

from datetime import datetime, timezone

import yaml

__version__ = '1.2'
__fileversion__ = '1.2'
__author__ = 'Matthew Varnam'


with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

sensor_config2 = config['sensors']
sensor_config2['Pyro_Up']    = {'serial_num': None, 'type': 'apogee_su', 'interval': 2000}
sensor_config2['Pyro_Down']  = {'serial_num': None, 'type': 'apogee_sd', 'interval': 2000}
sensor_config2['Pygeo_Up']   = {'serial_num': None, 'type': 'apogee_lu', 'interval': 2000}
sensor_config2['Pygeo_Down'] = {'serial_num': None, 'type': 'apogee_ld', 'interval': 2000}
sensor_config2['GPS']        = {'serial_num': None, 'type': 'gps'      , 'interval': 2000}

# =========================================================================
#  Logger to save measured data to files
# =========================================================================
class FileLogger(QObject):
    """Connects to emitters of data from sensors and writes to
    files in the data_logs folder."""
    update_sensor_request = Signal()

    def __init__(self, prefix="data_logs/", parent=None):
        super().__init__(parent)
        
        self.thermist_list = ['apogee_lu','apogee_ld']
        self.excitation_voltage = None
        self.loc = {'lat': None,
                    'lon': None,
                    'alt': None
                    }
        self.sensor_list = []
        
        # Create dictionary of properties for correctly formatting each sensor's data
        self.SENSOR_CONFIG = {                                # Convert to .yaml file

            'ada_as7341': {
                'file_prefix': f'{prefix}ada/',
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'channel_415'   : {'fmt':'.0f', 'header': '415 Channel'},
                    'channel_445'   : {'fmt':'.0f', 'header': '445 Channel'},
                    'channel_480'   : {'fmt':'.0f', 'header': '480 Channel'},
                    'channel_515'   : {'fmt':'.0f', 'header': '515 Channel'},
                    'channel_555'   : {'fmt':'.0f', 'header': '555 Channel'},
                    'channel_590'   : {'fmt':'.0f', 'header': '590 Channel'},
                    'channel_630'   : {'fmt':'.0f', 'header': '630 Channel'},
                    'channel_680'   : {'fmt':'.0f', 'header': '680 Channel'},
                    'channel_nir'   : {'fmt':'.0f', 'header': 'NIR Channel'},
                    'channel_clr'   : {'fmt':'.0f', 'header': 'CLR Channel'},
                    'exposure_t'    : {'fmt':'.0f', 'header': 'Exposure Time (ms)'},
                    }
                },
            
            'pim_bme280': {
                'file_prefix': f'{prefix}bme/',
                'fields': {
                    'timestamp'  : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'temperature': {'fmt':'.2f', 'header': 'Temperature (°C)'},
                    'pressure'   : {'fmt':'.1f', 'header': 'Temperature (hPa)'},
                    'humidity'   : {'fmt':'.2f', 'header': 'Humidity (%)'},
                    }
                },

            'gps'       : {
                'file_prefix': f'{prefix}gps/',
                'fields': {
                    'timestamp'  : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'lat'        : {'fmt':'.6f', 'header': 'Latitude (deg)'},
                    'lon'        : {'fmt':'.6f', 'header': 'Longitude (deg)'},
                    'alt'        : {'fmt':'.1f', 'header': 'Altitude (m)'}
                    }
                },
            
            'spn1'      : {
                'file_prefix': f'{prefix}spn1/', 
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'total'         : {'fmt':'.1f', 'header': 'Total (W/m2)'},
                    'diffuse'       : {'fmt':'.1f', 'header': 'Diffuse (W/m2)'},
                    'sun_state'     : {'fmt':'.0f', 'header': 'Sun bool'},
                    'case_temp'     : {'fmt':'.2f', 'header': "Case Temperature (°C)"}
                    }
                },
            
            'apogee_lu': {
                'file_prefix': f'{prefix}apogeeLU/',
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux': {'fmt':'.6f', 'header': 'Radiative Flux (W/m2)'},
                    'excite_v'      : {'fmt':'.6f', 'header': 'Excitation Voltage (V)'},
                    'sensor_t'      : {'fmt':'.6f', 'header': "Sensor Temperature (°C)" },
                    'voltage0'      : {'fmt':'.6f', 'header': 'Differential Voltage0 (V)' },
                    'voltage1'      : {'fmt':'.6f', 'header': 'Differential Voltage1 (V)' }
                    }
                },
            
            'apogee_ld': {
                'file_prefix': f'{prefix}apogeeLD/',
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux': {'fmt':'.6f', 'header': 'Radiative Flux (W/m2)'},
                    'excite_v'      : {'fmt':'.6f', 'header': 'Excitation Voltage (V)'},
                    'sensor_t'      : {'fmt':'.6f', 'header': "Sensor Temperature (°C)" },
                    'voltage0'      : {'fmt':'.6f', 'header': 'Differential Voltage0 (V)' },
                    'voltage1'      : {'fmt':'.6f', 'header': 'Differential Voltage1 (V)' }
                    }
                },
            
            'apogee_su': {
                'file_prefix': f'{prefix}apogeeSU/',
                'fields': {
                    'timestamp'      : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux' : {'fmt':'.6f', 'header': 'Radiative Flux Down (W/m2)'},
                    'voltage'        : {'fmt':'.6f', 'header': 'Differential Voltage Down (V)' }
                    }
                },
            
            'apogee_sd': {
                'file_prefix': f'{prefix}apogeeSD/',
                'fields': {
                    'timestamp'      : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux' : {'fmt':'.6f', 'header': 'Radiative Flux Down (W/m2)'},
                    'voltage'        : {'fmt':'.6f', 'header': 'Differential Voltage Down (V)'}
                    }
                },

            'spec': {
                'file_prefix': f'{prefix}spec/',
                'fields': {
                    'timestamp'      : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'y'              : {'fmt':'.1f', 'header': 'Counts'}
                    }
                },
            
            'alpha_opc': {
                'file_prefix': f'{prefix}opc/',
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    
                    # --- Particle Size Distributions ---
                    **{f'bin{i}':       {'fmt': '.6f', 'header': f'Bin{i} Count'} for i in range(24)},
                    **{f'bin{i}mtof':   {'fmt': '.2f', 'header': f'Bin{i} MToF'} for i in [1, 3, 5, 7]},
                      
                    # --- Mass Concentration Data (The Core Metrics) ---
                    'pm1':             {'fmt': '.2f', 'header': 'PM1 (ug/m3)'},
                    'pm2.5':           {'fmt': '.2f', 'header': 'PM2.5 (ug/m3)'},
                    'pm10':            {'fmt': '.2f', 'header': 'PM10 (ug/m3)'},
                    
                    # --- Diagnostic & Flow Calibration Data ---
                    'sfr':             {'fmt': '.3f', 'header': 'Flow Rate (L/min)'},
                    'sampling_period': {'fmt': '.2f', 'header': 'Sampling Period (s)'},
                    'laser_status':    {'fmt': '.0f', 'header': 'Laser Status (DAC)'},
                    
                    # --- On-board Meteorological Sensors ---
                    'temperature':     {'fmt': '.2f', 'header': 'Temperature (C)'},
                    'rh':              {'fmt': '.2f', 'header': 'Humidity (%)'},
                    }
                },
            
            'voltage':{
                'file_prefix':f'{prefix}voltage/',
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'excite_v'      : {'fmt':'.6f', 'header': 'Excitation Voltage (V)'}
                    }
                },

            'gas':{
                'file_prefix':f'{prefix}gas/',
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'mvolt'         : {'fmt':'.2f', 'header': 'Sensor Voltage (V)'},
                    'conc'          : {'fmt':'.1f', 'header': 'Gas Concentration (ppb)'}
                    }
                }
            }

        # Initialise empty names as output filepaths for each sensor
        for key in self.SENSOR_CONFIG.keys():
            self.SENSOR_CONFIG[key]['output_file'] = None

        self.current_uas_time = "00:00:00.000000"
        self.recording_active = False

    @Slot()
    def confirm_setup_complete(self):
        self.recording_active = True
        self.set_recording_state(True)

    @Slot(str)
    def handle_time(self, uas_time):
        if uas_time != datetime.fromtimestamp(0 / 1_000_000.0) and uas_time:
            self.current_uas_time = uas_time

    @Slot(str, str, dict)
    def handle_data(self, name, sensor_type, data_dict):

        sensor = self.SENSOR_CONFIG.get(sensor_type)
        fields_config = self.SENSOR_CONFIG[sensor_type]['fields']
        
        if not sensor:
            raise ValueError('Incorrect sensor name chosen')
            
        output_file = sensor['output_file']
        
        # Update excitation voltage to most recently measured value
        if sensor_type == 'voltage':
            if data_dict['excite_v'] > 2.5 and data_dict['excite_v'] < 3.5:
                self.excitation_voltage = data_dict['excite_v']
            else:
                self.excitation_voltage = None
        
        elif sensor_type == 'gps':
            for key in ['lat','lon','alt']:
                if data_dict[key] is not None:
                    self.loc[key] = data_dict[key]
        
        if not self.recording_active or (output_file is None):
            return
        
        # Recalculate longwave radiation from measured excitation voltage
        if sensor_type in self.thermist_list:
            if self.excitation_voltage is not None:
                voltage0, voltage1 = data_dict['voltage0'],data_dict['voltage1']
                
                ### HARDCODED ATM
                if sensor_type == 'apogee_lu':
                    serial_num = 'SL510_1729'
                elif sensor_type == 'apogee_ld':
                    serial_num = 'SL610_1463'
                k = find_coefficients(serial_num)

                tk, lw = calc_longwave(k, voltage0, voltage1, self.excitation_voltage)
                
                # Convert to Celcius from Kelvin
                tk = tk - 273.15
                
                # Change radiative flux based on measured voltage
                data_dict['radiative_flux'] = lw
                data_dict['sensor_t'] = tk
                data_dict['excite_v'] = self.excitation_voltage
        
        # Save the data by opening file and constructing string
        if output_file and not output_file.closed:
            line = f"{self.current_uas_time}"
            
            values_list = []

            for k in fields_config.keys():
                fmt = fields_config[k]['fmt']
                values_list.append(f"{data_dict[k]:{fmt}}")

            values = ", ".join(values_list)
            
            output_file.write(line + values + "\n")
            output_file.flush()
        
    @Slot(str, str, dict)
    def handle_spec(self, name, sensor_type, data_dict):

        sensor_info = self.SENSOR_CONFIG.get(sensor_type)

        self.request_sensor_list()  #TESTING PURPOSES ONLY

        if not sensor_info:
            raise ValueError('Incorrect sensor name chosen')

        if not self.recording_active:
            return
        
        if self.nspec > 99999:
            # Set the timestamp that names each file created
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.SENSOR_CONFIG[sensor_type]['output_file'] = sensor_info['file_prefix'] + timestamp
            Path(sensor_info['output_file']).mkdir(parents=True, exist_ok=True)
            self.nspec = 0

        prefix = sensor_info['output_file']
        
        spec_fname = f'{prefix}/spectrum_{self.nspec:05d}' + '.txt'

        correct_dark_counts  = 'None'
        correct_nonlinearity = 'None'

        if self.current_uas_time != "00:00:00.000000":
            timestamp = self.current_uas_time
        else:
            timestamp = data_dict['timestamp']

        h = 'Avaspec spectrum file, generated by iFit\n' \
                + f'filename; {os.path.split(spec_fname)[-1]}\n' \
                + f'serial_number; {data_dict['serial_number']}\n' \
                + f'spectrum_number; {self.nspec}\n' \
                + f'integration_time; {data_dict['integration_time']}\n' \
                + f'coadds; {data_dict['coadds']}\n' \
                + f'timestamp; {timestamp}\n' \
                + f'elecdk_correction; {correct_dark_counts}\n' \
                + f'nonlin_correction; {correct_nonlinearity}\n' \
                + f'lat; {self.loc['lat']}\n' \
                + f'lon; {self.loc['lon']}\n' \
                + f'alt; {self.loc['alt']}\n' \
                + 'Wavelength (nm),       Intensity (arb)'

        x = data_dict['x']
        y = data_dict['y']

        # Output final spectra
        fmt = '%.5e', '%1.5e'
        np.savetxt(spec_fname, np.column_stack([x, y]), header=h, fmt = fmt)

        line = f"{self.current_uas_time}"

        self.nspec += 1

    #### NEED TO UPDATE THIS FUNCTION SO IT IS BLOCKING!!!
    def request_sensor_list(self):
        """Update the list of sensors to record data from."""
        self.update_sensor_request.emit()

    @Slot(list)
    def update_sensor_list(self, sensor_list):
        self.sensor_list = sensor_list
        #print(self.sensor_list)

    @Slot(bool)
    def set_recording_state(self, state):

        # Set variable for the current recording state
        self.recording_active = state
        all_keys = list(self.SENSOR_CONFIG.keys())
        
        # --- START RECORDING: Create New Files ---
        if state:
            # Update list of sensors currently connected
            self.request_sensor_list()

            # Set the timestamp that names each file created
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            # Check that the folder
            for name in self.sensor_list:

                sensor_type = sensor_config2[name]['type']
                sensor_info = self.SENSOR_CONFIG.get(sensor_type)

                print(name)
                # Search for the directory and create the folder if it does not exist
                Path(sensor_info['file_prefix']).mkdir(parents=True, exist_ok=True)
                
                if name == 'UV_Spec':
                    self.nspec = 0
                    filename = sensor_info['file_prefix']+ timestamp

                    Path(sensor_info['file_prefix']+timestamp).mkdir(parents=True, exist_ok=True)
                    self.SENSOR_CONFIG[sensor_type]['output_file'] = filename

                else:    
                    filename = sensor_info['file_prefix']+ timestamp
                    output_file = open(filename +'.txt', "w")
                    output_file.write(f"MACE File Version {__fileversion__}\n")
                    
                    # Base metadata headers
                    base_headers = ["UAS Time", "Local RX Time (ns)"]
                    
                    # Extract custom sensor headers in their defined order
                    sensor_headers = [info['header'] for info in sensor_info['fields'].values()]
                    
                    # Combine them into a single comma-separated line
                    full_header_line = ", ".join(base_headers + sensor_headers)
                    
                    output_file.write(full_header_line + '\n')
                    
                    self.SENSOR_CONFIG[sensor_type]['output_file'] = output_file

            print(f"[*] Started recording at {timestamp}")
            
        else:
            # --- STOP RECORDING: Close Current File ---
            for name in self.sensor_list:
                sensor_type = sensor_config2[name]['type']
                sensor_info = self.SENSOR_CONFIG.get(sensor_type)
                if name != 'UV_Spec' and sensor_info['output_file'] is not None:
                    sensor_info['output_file'].close()
                    sensor_info['output_file'] = None
                                
                print("[!] Recording stopped and file closed at {timestamp}.")
            
    def close_file(self):
        
        # --- STOP RECORDING: Close Current File ---
        for name in self.sensor_list:
            sensor_type = sensor_config2[name]['type']
            sensor_info = self.SENSOR_CONFIG.get(sensor_type)
            if name != 'UV_Spec' and sensor_info['output_file'] is not None:
                sensor_info['output_file'].close()
                sensor_info['output_file'] = None