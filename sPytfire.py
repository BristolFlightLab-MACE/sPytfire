# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 11:13:23 2026

Datalogger for the MACE drones, with some code built on iFit SO2 emission rate frame *Not yet included

Use the following lines in conda to make sure all modules are installed for iFit and MACE drone
conda install -c conda-forge numpy scipy tqdm pandas pyyaml pyserial utm pyside6 pyqtgraph seabreeze
pip install pyqtdarktheme

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk

"""

# =============================================================================
# Manual inputs
# =============================================================================
__version__ = '1.2'
__fileversion__ = '1.2'
__author__ = 'Matthew Varnam'

# Manual change to on/off recording channel
on_off_channel = 11

# Manual change to mavlink connection string
# connection_str = "COM6"
# connection_str = "/dev/ttyS0"
connection_str = "/dev/serial0"

# Specify sensor payload
### TO IMPLEMENT

# =========================================================================
#  Early processing
# =========================================================================

# Import pyside6 to create the process for reading data in to an application
from PySide6.QtCore import QObject, QThread, Slot, QTimer, QCoreApplication, Qt, Signal, QEventLoop

# Load custom modules containing the workers for each sensor/connection
from spytfire.apogee_sensor import ApogeeSensorWorker, calc_longwave
from spytfire.bme_sensor import BMESensorWorker
from spytfire.adafruit_sensor import AdafruitSensorWorker
from spytfire.opc_sensor import OPCSensorWorker
from spytfire.spectrometer_sensor import SpecSensorWorker
from spytfire.spn1_sensor import SPN1SensorWorker
from spytfire.voltage_sensor import VoltageSensorWorker
from spytfire.mavlink import MavlinkWorker
from spytfire.base import SensorWorker, UASWorker

# Load other libraries
from pathlib import Path
from datetime import datetime, timezone
import sys, signal

import numpy as np

Path("data_logs").mkdir(parents=True, exist_ok=True)

# ---------------- Output Handlers ----------------
class ConsoleLogger(QObject):
    """Connects to emitters of data from sensors and prints
    results to console."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    # Create separate slot to print the time as it arrives from MAVLINK
    @Slot(str)
    def handle_time(self, uas_time):

        pass
        #print(f"[Time] {uas_time}")

    # Crate a slot for the arrival of data from the sensors
    @Slot(str, dict)
    def handle_data(self, name, data_dict):
        #pass
        print(name)

        for key in data_dict:
            if key != 'y':
                print(f"{key}:{data_dict[key]:.6f}")
            else:
                print([np.array2string(v, precision=1, floatmode='fixed') if isinstance(v, np.ndarray) else str(v) 
       for v in data_dict[key]])

    # Create a dummy slot to ignore the arrival of data from the spectrometer            
    @Slot(str, dict)
    def handle_spec(self, name, data_dict):
        pass

class FileLogger(QObject):
    """Connects to emitters of data from sensors and writes to
    files in the data_logs folder."""
    update_sensor_request = Signal()

    def __init__(self, prefix="data_logs/", parent=None):
        super().__init__(parent)
        
        self.thermist_list = ['SL510_1729','SL610_1463']
        self.excitation_voltage = None
        self.sensor_list = []
        
        # Create dictionary of properties for correctly formatting each sensor's data
        self.SENSOR_CONFIG = {

            'AdaFruit': {
                'file_prefix': f'{prefix}ada/',
                'output_file': None,
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
            
            'BME280': {
                'file_prefix': f'{prefix}bme/',
                'output_file': None,
                'fields': {
                    'timestamp'  : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'temperature': {'fmt':'.2f', 'header': 'Temperature (°C)'},
                    'pressure'   : {'fmt':'.1f', 'header': 'Temperature (hPa)'},
                    'humidity'   : {'fmt':'.2f', 'header': 'Humidity (%)'},
                    }
                },

            'GPS'       : {
                'file_prefix': f'{prefix}gps/',
                'output_file': None,
                'fields': {
                    'timestamp'  : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'lat'        : {'fmt':'.6f', 'header': 'Latitude (deg)'},
                    'lon'        : {'fmt':'.6f', 'header': 'Longitude (deg)'},
                    'alt'        : {'fmt':'.1f', 'header': 'Altitude (m)'}
                    }
                },
            
            'SPN1'      : {
                'file_prefix': f'{prefix}spn1/', 
                'output_file': None,
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'total'         : {'fmt':'.1f', 'header': 'Total (W/m2)'},
                    'diffuse'       : {'fmt':'.1f', 'header': 'Diffuse (W/m2)'},
                    'sun_state'     : {'fmt':'.0f', 'header': 'Sun bool'},
                    'case_temp'     : {'fmt':'.2f', 'header': "Case Temperature (°C)"}
                    }
                },
            
            'SL510_1729': {
                'file_prefix': f'{prefix}apogeeLU/',
                'output_file': None,
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux': {'fmt':'.6f', 'header': 'Radiative Flux (W/m2)'},
                    'excite_v'      : {'fmt':'.6f', 'header': 'Excitation Voltage (V)'},
                    'sensor_t'      : {'fmt':'.6f', 'header': "Sensor Temperature (°C)" },
                    'voltage0'      : {'fmt':'.6f', 'header': 'Differential Voltage0 (V)' },
                    'voltage1'      : {'fmt':'.6f', 'header': 'Differential Voltage1 (V)' }
                    }
                },
            
            'SL610_1463': {
                'file_prefix': f'{prefix}apogeeLD/',
                'output_file': None,
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux': {'fmt':'.6f', 'header': 'Radiative Flux (W/m2)'},
                    'excite_v'      : {'fmt':'.6f', 'header': 'Excitation Voltage (V)'},
                    'sensor_t'      : {'fmt':'.6f', 'header': "Sensor Temperature (°C)" },
                    'voltage0'      : {'fmt':'.6f', 'header': 'Differential Voltage0 (V)' },
                    'voltage1'      : {'fmt':'.6f', 'header': 'Differential Voltage1 (V)' }
                    }
                },
            
            'SP510_3985': {
                'file_prefix': f'{prefix}apogeeS/',
                'output_file': None,
                'fields': {
                    'timestamp'      : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux0': {'fmt':'.6f', 'header': 'Radiative Flux Down (W/m2)'},
                    'voltage0'       : {'fmt':'.6f', 'header': 'Differential Voltage Down (V)' },
                    'radiative_flux1': {'fmt':'.6f', 'header': 'Radiative Flux Up (W/m2)'},
                    'voltage1'       : {'fmt':'.6f', 'header': 'Differential Voltage Up (V)' }
                    }
                },
            
            # Note currently not in use due to two shortwave sensors connecting to the same ADC
            'SP610_1707': {
                'file_prefix': f'{prefix}apogeeS/',
                'output_file': None,
                'fields': {
                    'timestamp'      : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'radiative_flux0': {'fmt':'.6f', 'header': 'Radiative Flux Down (W/m2)'},
                    'voltage0'       : {'fmt':'.6f', 'header': 'Differential Voltage Down (V)'},
                    'radiative_flux1': {'fmt':'.6f', 'header': 'Radiative Flux Up (W/m2)'},
                    'voltage1'       : {'fmt':'.6f', 'header': 'Differential Voltage Up (V)'}
                    }
                },

            '7616940SP': {
                'file_prefix': f'{prefix}spec/',
                'output_file': None,
                'fields': {
                    'timestamp'      : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'y'              : {'fmt':'.1f', 'header': 'Counts'}
                    }
                },
            
            'OPC_N3': {
                'file_prefix': f'{prefix}opc/',
                'output_file': None,
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
            
            'Ex_volt':{
                'file_prefix':f'{prefix}voltage/',
                'output_file': None,
                'fields': {
                    'timestamp'     : {'fmt':'.0f', 'header': 'Time (ns)'},
                    'excite_v'      : {'fmt':'.6f', 'header': 'Excitation Voltage (V)' }
                    }
                }
            }
        
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

    @Slot(str, dict)
    def handle_data(self, name, data_dict):

        sensor = self.SENSOR_CONFIG.get(name)
        fields_config = self.SENSOR_CONFIG[name]['fields']
        
        if not sensor:
            raise ValueError('Incorrect sensor name chosen')
            
        output_file = sensor['output_file']
        
        # Update excitation voltage to most recently measured value
        if name == 'Ex_volt':
            if data_dict['excite_v'] > 2.5 and data_dict['excite_v'] < 3.5:
                self.excitation_voltage = data_dict['excite_v']
            else:
                self.excitation_voltage = None    
        
        if not self.recording_active or (output_file is None):
            return
        
        # Recalculate longwave radiation from measured excitation voltage
        if name in self.thermist_list:
            if self.excitation_voltage is not None:
                voltage0 = data_dict['voltage0']
                voltage1 = data_dict['voltage1']
                model = name
                
                tk, lw = calc_longwave(model, voltage0, voltage1, self.excitation_voltage)
                
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
        
    @Slot(str, dict)
    def handle_spec(self, name, data_dict):

        sensor_info = self.SENSOR_CONFIG.get(name)
        fields_config = self.SENSOR_CONFIG[name]['fields']

        self.request_sensor_list()  #TESTING PURPOSES ONLY

        if not sensor_info:
            raise ValueError('Incorrect sensor name chosen')

        if not self.recording_active:
            return
        
        if self.nspec > 99999:
            # Set the timestamp that names each file created
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.SENSOR_CONFIG[name]['output_file'] = sensor_info['file_prefix'] + timestamp
            Path(sensor_info['output_file']).mkdir(parents=True, exist_ok=True)
            self.nspec = 0

        prefix = sensor_info['output_file']
        
        spec_fname = f'{prefix}/spectrum_{self.nspec:05d}'

        output_file = open(spec_fname +'.txt', "w")

        line = f"{self.current_uas_time}"

        values_list = []
        for k in fields_config.keys():
            if k != 'y':
                fmt = fields_config[k]['fmt']
                values_list.append(f"{data_dict[k]:{fmt}}")
            else:
                fmt = fields_config[k]['fmt']
                values_list.extend(f"{elem:{fmt}}" for elem in data_dict[k])

        values = ", ".join(values_list)

        output_file.write(line + values + "\n")
        output_file.flush()
        output_file.close()

        print('saved spectrum{:05d}'.format(self.nspec))
        self.nspec += 1

    #### NEED TO UPDATE THIS FUNCTION SO IT IS BLOCKING!!!
    def request_sensor_list(self):
        """Update the list of sensors to record data from."""
        self.update_sensor_request.emit()

    @Slot(list)
    def update_sensor_list(self, sensor_list):
        self.sensor_list = sensor_list
        print(self.sensor_list)

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
                sensor_info = self.SENSOR_CONFIG.get(name)

                # Search for the directory and create the folder if it does not exist
                Path(sensor_info['file_prefix']).mkdir(parents=True, exist_ok=True)
                
                if name == '7616940SP':
                    self.nspec = 0
                    filename = sensor_info['file_prefix']+ timestamp

                    Path(sensor_info['file_prefix']+timestamp).mkdir(parents=True, exist_ok=True)
                    self.SENSOR_CONFIG[name]['output_file'] = filename

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
                    
                    self.SENSOR_CONFIG[name]['output_file'] = output_file

            print(f"[*] Started recording at {timestamp}")
            
        else:
            # --- STOP RECORDING: Close Current File ---
            for name in all_keys:
                if name != '7616940SP' and self.SENSOR_CONFIG[name]['output_file'] is not None:
                    self.SENSOR_CONFIG[name]['output_file'].close()
                    self.SENSOR_CONFIG[name]['output_file'] = None
                                
                print("[!] Recording stopped and file closed at {timestamp}.")
            
    def close_file(self):
        all_keys = list(self.SENSOR_CONFIG.keys())
        
        # --- STOP RECORDING: Close Current File ---
        for name in all_keys:
            if name != '7616940SP' and self.SENSOR_CONFIG[name]['output_file'] is not None:
                self.SENSOR_CONFIG[name]['output_file'].close()
                self.SENSOR_CONFIG[name]['output_file'] = None

# ---------------- Controller ----------------

class Controller(QObject):
    """Setup all emitters and handles while launching each sensor."""
    setup_complete = Signal()
    sensor_list = Signal(list)

    def __init__(self, handlers, conn_str, rc_channel):
        super().__init__()
        self.handlers = handlers
        self.threads = []
        self.workers = []

        # Setup MAVLINK
        self._add_mavlink(conn_str, rc_channel)

        # Setup UAS Time
        if self.mav_worker.is_initialized == True:
            self._add_uas_time()
        
        # Setup Sensors
        self.add_sensor('AdaFruit',   sensor_type = 'adafruit')
        self.add_sensor('BME280'  ,   sensor_type = 'bme280')
        self.add_sensor('SL510_1729', sensor_type = 'apogee')
        self.add_sensor('SL610_1463', sensor_type = 'apogee')
        self.add_sensor('SP510_3985', sensor_type = 'apogee')
        self.add_sensor('SPN1',       sensor_type = 'spn1')
        self.add_sensor('7616940SP',  sensor_type = 'spec')
        self.add_sensor('OPC_N3',     sensor_type = 'opc')
        self.add_sensor('Ex_volt',    sensor_type = 'voltage')

        for handler in self.handlers:
            if hasattr(handler, "update_sensor_list"):
                handler.update_sensor_request.connect(self.monitor_workers)
                self.sensor_list.connect(handler.update_sensor_list)
        
        for handler in self.handlers:
            if hasattr(handler, "confirm_setup_complete"):
                self.setup_complete.connect(handler.confirm_setup_complete)
        
        self.setup_complete.emit()

    def _add_mavlink(self, conn_str, rc_channel):
        # Create the worker
        self.mav_worker = MavlinkWorker(conn_str,channel_num = rc_channel)
        
        # Create a new QThread, then move the worker onto the thread
        thread = QThread()
        self.mav_worker.moveToThread(thread)
        
        # Execute functions on starting and finishing the thread
        thread.started.connect(self.mav_worker.start_work)
        thread.finished.connect(self.mav_worker.deleteLater)       # Clean exit
        
        # Wire up the mavlink worker's recording bool change to filelogger
        for handler in self.handlers:
            if hasattr(handler, "set_recording_state"):
                self.mav_worker.recording_trigger.connect(handler.set_recording_state)
        
        for handler in self.handlers:
            self.mav_worker.data_ready.connect(handler.handle_data)
          
        self.threads.append(thread)
        self.workers.append(self.mav_worker)
        thread.start()    
        
    def _add_uas_time(self):
        # Create the worker
        self.uas_worker = UASWorker("UAS_Time")
        
        # Create a new QThread, then move the worker onto the thread
        thread = QThread()
        self.uas_worker.moveToThread(thread)
        
        thread.finished.connect(self.uas_worker.deleteLater)
        
        # Connect emitted updates from mav_worker to the uas_worker update
        self.mav_worker.uas_time_updated.connect(
            self.uas_worker.update_from_mavlink, 
            type=Qt.QueuedConnection
            )
        
        for handler in self.handlers:
            if hasattr(handler, "handle_time"):
                self.uas_worker.data_ready.connect(handler.handle_time)
        
        self.threads.append(thread)
        self.workers.append(self.uas_worker)
        thread.start()
    
    def add_sensor(self, name, sensor_type = 'default'):
                
        # Define a configuration map for your sensors
        sensor_map = {
            'adafruit': (AdafruitSensorWorker, 2000),
            'bme280':   (BMESensorWorker, 500),
            'apogee':   (ApogeeSensorWorker, 1000),
            'spn1':     (SPN1SensorWorker, 1000),
            'voltage':  (VoltageSensorWorker, 500),
            'opc':      (OPCSensorWorker, 1000),
            'spec':     (SpecSensorWorker, 5000),
        }

        # Retrieve the class and interval, falling back to defaults
        worker_class, interval = sensor_map.get(sensor_type, (SensorWorker, 1000))
        if sensor_type == 'spec':
            worker = worker_class(name)
        
        else:
            worker = worker_class(name, interval_ms=interval)

        if sensor_type not in sensor_map:
            print(f"WARNING: Default Worker created for type '{sensor_type}'")
        
        # Check that the worker has been created, and if not, skip the thread handoff
        if not worker.is_initialized:

            # Ensure cleanup of any partial objects
            worker.deleteLater() 
            return # Exit the function so no thread is started
        
        # Configure QThreads
        thread = QThread()
        worker.moveToThread(thread)
        
        thread.started.connect(worker.start_work)
        thread.finished.connect(worker.deleteLater)
        
        for handler in self.handlers:
            if sensor_type == 'spec':
                worker.data_ready.connect(handler.handle_spec)
            else:
                worker.data_ready.connect(handler.handle_data)
        
        self.threads.append(thread)
        self.workers.append(worker)
        
        thread.start()

    @Slot()
    def monitor_workers(self):
        self.curr_workers = []
        for worker in self.workers:
            if worker.is_initialized:
                self.curr_workers.append(worker.name)
        self.sensor_list.emit(self.curr_workers)

    def request_exit(self):
        """Called DIRECTLY by the signal handler."""
        print("\nCtrl+C detected — performing shutdown...")
        
        # Stop workers using signals
        for worker in self.workers:
            try:
                if worker is not None:
                    # Terminate connections first
                    worker._safe_shutdown(reason="User Interrupt (Ctrl+C)")
                    
                    # Kill timers that are present
                    worker.stop_requested.emit()
                
            except RuntimeError:
                pass
            
        # Tell threads to stop their event loops
        for thread in self.threads:
            thread.quit()
            
        # Cleanup FileLogger and Console Logger handlers 
        for handler in self.handlers:
            if hasattr(handler, "close_file"):
                handler.close_file()

        print("Cleanup complete")
        QCoreApplication.instance().quit()

# ---------------- Main ----------------

if __name__ == "__main__":
        
    # =========================================================================
    # Create PySide Application
    # =========================================================================
    app = QCoreApplication(sys.argv)

    # The "Python Heartbeat" Timer
    # This allows the interpreter to process SIGINT (Ctrl+C)
    exit_timer = QTimer()
    exit_timer.timeout.connect(lambda: None)
    exit_timer.start(100)

    # Setup logging and controller components
    console_logger = ConsoleLogger()
    file_logger = FileLogger()
    controller = Controller([console_logger, file_logger], connection_str, on_off_channel)

    # Hook Ctrl+C
    signal.signal(signal.SIGINT, lambda sig, frame: (exit_timer.stop(), controller.request_exit()))

    sys.exit(app.exec())
