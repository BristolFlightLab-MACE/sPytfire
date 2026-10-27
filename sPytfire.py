# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 11:13:23 2026

Datalogger for the MACE drones, with some code built on iFit SO2 emission rate frame *Not yet included

Use the following lines in conda to make sure all modules are installed for iFit and MACE drone
conda install -c conda-forge numpy scipy tqdm pandas pyyaml pyserial utm pyside6 pyqtgraph seabreeze
pip install pyqtdarktheme

@author: Matt Varnam
@email: matt(dot)varnam

"""

# =============================================================================
# Manual inputs
# =============================================================================

# Manual change to on/off recording channel
on_off_channel = 11
heater_channel0 = 12
heater_channel1 = 13

# Manual change to mavlink connection string
# connection_str = "COM6"
# connection_str = "/dev/ttyS0"
#connection_str = "/dev/serial0"
connection_str = "udpin:192.168.137.51:14550"

# =========================================================================
#  Define imports
# =========================================================================

import os
if os.name == "nt":
    frequency_Hz = 100000
    os.environ["BLINKA_MCP2221"] = "1"
    os.environ["BLINKA_MCP2221_I2C_FREQUENCY"] = str(frequency_Hz)

# This annoyingly has to be hear to make sure board imports correctly on Windows
import board

# Import pyside6 to create the process for reading data in to an application
from PySide6.QtCore import QObject, QThread, Slot, QTimer, QCoreApplication, Qt, Signal, QEventLoop

from spytfire.i2c import I2CManager
from spytfire.relay import RelayControl
from spytfire.base import SensorWorker, UASWorker
from spytfire.mavlink import MavlinkWorker

from spytfire.logger.console import ConsoleLogger
from spytfire.logger.file import FileLogger
from spytfire.logger.analysis import AnalysisLogger

# Load custom modules containing the workers for each sensor/connection
from spytfire.sensor.adafruit import AdafruitSensorWorker
from spytfire.sensor.apogee import ApogeeSensorWorker
#from spytfire.sensor.bme import BMESensorWorker
from spytfire.sensor.bme_adafruit import BMESensorWorker
from spytfire.sensor.gas import GasSensorWorker
from spytfire.sensor.gas_4AFE import AFESensorWorker
from spytfire.sensor.pt1000 import PT1000SensorWorker
from spytfire.sensor.opc import OPCSensorWorker
from spytfire.sensor.spectrometer import SpecWorker
from spytfire.sensor.spn1 import SPN1SensorWorker
from spytfire.sensor.voltage import VoltageSensorWorker
from spytfire.sensor.dummy_spectrometer import DummySpecWorker

# Load other libraries
from pathlib import Path
import sys
import signal as pysignal
import yaml

# Create an automatic directory to store output data
Path("data_logs").mkdir(parents=True, exist_ok=True)

# Load predetermined configuration
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

if config is None:
    raise ValueError("config.yaml is invalid format or does not exist. Please provide a valid configuration file.")

if config.get('sensors') is None:
    raise ValueError("No sensor configuration found in config.yaml. Please provide a valid configuration file.")

sensor_config = config['sensors']

# Map sensor types to their worker classes
SENSOR_TYPE_TO_WORKER = {
    'ada_as7341': AdafruitSensorWorker,
    'pim_bme280': BMESensorWorker,
    'apogee'    : ApogeeSensorWorker,
    'spn1'      : SPN1SensorWorker,
    'voltage'   : VoltageSensorWorker,
    'alpha_opc' : OPCSensorWorker,
    'spec'      : SpecWorker,
    'alpha_gas' : GasSensorWorker,
    'alpha_afe' : AFESensorWorker,
    'pt1000'    : PT1000SensorWorker,
    'fake_spec' : DummySpecWorker,
    'default'   : SensorWorker
}

# Build a combined sensor info mapping from config file
SENSOR_INFO = {
    name: {
        'serial_num': sensor_config['serial_num'],
        'type': sensor_config['type'],
        'address':sensor_config['address'],
        'worker_class': SENSOR_TYPE_TO_WORKER.get(sensor_config['type'], SensorWorker),
        'interval': sensor_config.get('interval', 1000),
    }
    for name, sensor_config in config.get('sensors', {}).items()
}

# =========================================================================
#  Key controller class, holding the sensor objects once created
# =========================================================================

class Controller(QObject):
    """Setup all emitters and handles while launching each sensor."""
    setup_complete = Signal()
    sensor_list = Signal(list)

    def __init__(self, handlers, conn_str, rc_channel, heater_channel):
        super().__init__()
        self.handlers = handlers
        self.threads = []
        self.workers = []

        self._connect_analysis()

        # Setup MAVLINK
        self._add_mavlink(conn_str, rc_channel, heater_channel)

        # Setup UAS Time
        if self.mav_worker.is_initialized:
            self._add_uas_time()

        # Setup the I2C bus manager and set multiplex to False for now
        self.i2cbus_manager0 = I2CManager(multiplex=False,type='board')
        #self.i2cbus_manager1 = I2CManager(multiplex=False,type='smbus2',i2cline=2)

        # Setup relay control
        self.relay_control = RelayControl()
        if self.relay_control.is_initialized:
            self.mav_worker.heater_trigger.connect(self.switch_relay)

        # Setup Sensors
        for name, info in SENSOR_INFO.items():
            self.add_sensor(
                name,
                info['serial_num'],
                sensor_type =info['type'],
                address     =info['address'],
                worker_class=info['worker_class'],
                interval    =info['interval']
            )

        self._connect_handlers()
        self.setup_complete.emit()

    def _connect_handlers(self):
        for handler in self.handlers:
            if hasattr(handler, "update_sensor_list"):
                handler.update_sensor_request.connect(self.monitor_workers)
                self.sensor_list.connect(handler.update_sensor_list)

            if hasattr(handler, "confirm_setup_complete"):
                self.setup_complete.connect(handler.confirm_setup_complete)

    def _add_mavlink(self, conn_str, rc_channel0, rc_channel1):
        # Create the worker
        self.mav_worker = MavlinkWorker(conn_str,channel_num0 = rc_channel0, channel_num1 = rc_channel1)
        
        # Create a new QThread, then move the worker onto the thread
        thread = QThread()
        self.mav_worker.moveToThread(thread)
        
        # Execute functions on starting and finishing the thread
        thread.started.connect(self.mav_worker.start_work)
        thread.finished.connect(self.mav_worker.deleteLater)       # Clean exit
        
        # Connect Slots to handle worker emitted signals
        for handler in self.handlers:
            if hasattr(handler, "set_recording_state"):
                self.mav_worker.recording_trigger.connect(handler.set_recording_state)
        
            if hasattr(handler, "handle_data"):
                self.mav_worker.data_ready.connect(handler.handle_data)

        self.threads.append(thread)
        self.workers.append(self.mav_worker)
        thread.start()    

    @Slot(bool)
    def switch_relay(self, state):
        if state:
            self.relay_control.relay_on()
        else:
            self.relay_control.relay_off()

    def _add_uas_time(self):
        # Create the worker
        self.uas_worker = UASWorker("UAS_TIME")
        
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

    def add_sensor(self, name, serial_num, address, worker_class, sensor_type='default', interval=1000):

        # Retrieve the class and interval, falling back to defaults
        worker_class = worker_class

        if worker_class is SensorWorker:
            print(f"WARNING: Default Worker created for sensor_type '{sensor_type}'")
        
        self.i2cbus = self.i2cbus_manager0.get_channel(address)
        
        worker = worker_class(
            name=name,
            serial_num=serial_num,
            address=address,
            interval_ms=interval,
            i2cbus=self.i2cbus,
        )
        
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
                if hasattr(handler, "handle_data"):
                    worker.data_ready.connect(handler.handle_data)
        
        self.threads.append(thread)
        self.workers.append(worker)
        
        thread.start()

    def _connect_analysis(self):
        for handler in self.handlers:
            if hasattr(handler, "add_so2_analysis"):
                for handler2 in self.handlers:
                    if hasattr(handler2, "handle_data"):
                        handler.worker.data_ready.connect(handler2.handle_data)

    @Slot()
    def monitor_workers(self):
        self.curr_workers = []
        for worker in self.workers:
            if worker.is_initialized:
                match worker.name:
                    case 'MAVLink':
                        self.curr_workers.append('GPS')
                        self.curr_workers.append('IMU')
                    case 'UAS_TIME':
                        pass
                    case 'Pyronometer':
                        self.curr_workers.append('Pyro_Up')
                        self.curr_workers.append('Pyro_Down')
                    case 'CO2_HCl':
                        self.curr_workers.append('Alpha_HCl')
                        self.curr_workers.append('Alpha_CO2')
                    case 'NO2_O3':
                        self.curr_workers.append('Alpha_NO2')
                        self.curr_workers.append('Alpha_O3')
                    case 'H2S_SO2':
                        self.curr_workers.append('Alpha_H2S')
                        self.curr_workers.append('Alpha_SO2')
                    case 'UV_Spec':
                        self.curr_workers.append('UV_Spec')
                        self.curr_workers.append('Dark_Spec')
                        self.curr_workers.append('SO2_Col')
                    case _:
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
            
        # Tell threads to stop their event loops and wait for them to exit
        for thread in self.threads:
            thread.quit()
            thread.wait(1000)

        # Close the I2C bus manager
        if self.i2cbus_manager0.is_initialized:
            self.i2cbus_manager0.close()
            self.i2cbus_manager0 = None

        if self.relay_control.is_initialized:
            self.relay_control.close()
            self.relay_control = None
            
        # Cleanup FileLogger and Console Logger handlers 
        for handler in self.handlers:
            if hasattr(handler, "close_file"):
                handler.close_file()

        print("Cleanup complete")
        QCoreApplication.instance().quit()

# ---------------- Main ----------------
def main():        
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
    analysis_logger = AnalysisLogger()
    controller = Controller([console_logger, file_logger, analysis_logger],
                             connection_str,
                             on_off_channel,
                             heater_channel0)

    # Hook Ctrl+C
    pysignal.signal(pysignal.SIGINT, lambda sig, frame: (exit_timer.stop(), controller.request_exit()))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
