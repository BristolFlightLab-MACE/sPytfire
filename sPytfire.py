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

# Manual change to on/off recording channel
on_off_channel = 11

# Manual change to mavlink connection string
# connection_str = "COM6"
# connection_str = "/dev/ttyS0"
connection_str = "/dev/serial0"

# =========================================================================
#  Define imports
# =========================================================================

# Import pyside6 to create the process for reading data in to an application
from PySide6.QtCore import QObject, QThread, Slot, QTimer, QCoreApplication, Qt, Signal, QEventLoop

# Load custom modules containing the workers for each sensor/connection
from spytfire.sensor.apogee_sensor import ApogeeSensorWorker
from spytfire.sensor.bme_sensor import BMESensorWorker
from spytfire.sensor.adafruit_sensor import AdafruitSensorWorker
from spytfire.sensor.opc_sensor import OPCSensorWorker
from spytfire.sensor.spectrometer_sensor import SpecWorker
from spytfire.sensor.spn1_sensor import SPN1SensorWorker
from spytfire.sensor.voltage_sensor import VoltageSensorWorker
from spytfire.mavlink import MavlinkWorker
from spytfire.base import SensorWorker, UASWorker
from spytfire.logger.console_logger import ConsoleLogger
from spytfire.logger.file_logger import FileLogger

# Load other libraries
from pathlib import Path
import sys
import signal as pysignal

Path("data_logs").mkdir(parents=True, exist_ok=True)

# =========================================================================
#  Key controller class, holding the sensor objects once created
# =========================================================================

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
            'spec':     (SpecWorker, 5000),
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
    pysignal.signal(pysignal.SIGINT, lambda sig, frame: (exit_timer.stop(), controller.request_exit()))

    sys.exit(app.exec())
