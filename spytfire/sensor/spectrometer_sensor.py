"""
Created on Tue Mar 31 11:39:00 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# =============================================================================
# Define imports
# =============================================================================

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BaseWorker
from spytfire.spectra_analysis import AnalysisWorker # Not implemented

# avaspec.py is provided by Avantes and is used to control the spectrometer
# avaspecx64.dll is also require for Windows, or libavs_0.9.14.0_arm64.deb for 
# ARM-powered Linux (e.g., Raspberry Pi).
import spytfire.sensor.avaspec as av
import spytfire.sensor.av_errors as av_errors

# Import pyside6 to create the process for reading data in to an application
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QCoreApplication, Qt

# Import random to provide random inputs for the demonstration SensorWorker
import random

# Provides some useful time options
from datetime import datetime, timezone

# Useful for array manipulation and spectra averaging
import numpy as np

# Allow timestamping immediately upon data acquisition
import time

# =============================================================================
# Create new BaseWorker for the avaspec spectrometers
# =============================================================================

class SpecWorker(BaseWorker):
    '''Class to operate an Avaspec spectrometer and emit data to Controller.'''
    data_ready = Signal(str, str, dict)
    
    def __init__(self, name, serial_num = None, interval_ms = None):
        """
        Operates an Avaspec Nexos spectrometer using the
        BaseWorker class. 
        
        ***Code structure may change to more easily substitute different
        spectrometers

        Parameters
        ----------
        name : string
            A unique ID for the specific sensor in use
        
        Attributes
        ----------
        spectro : 
            Currently use spectro as the connection attribute rather than
            sensor to match iFit formatting
        is_initialized : bool
            Value that can be read outside the class to monitor the connection

        Emits
        ----------
        data_ready : dictionary
            A dictionary object containing the full spectrum measured by
            the spectrometer as well as the timestamp recorded by the
            sensor payload computer

        """      
                
        # Pass shared variables to BaseWorker
        super().__init__(name, serial_num, interval_ms)

        # Set some global paramters that are used in process()
        self.spectro = None
        self.pixels = 4096
        self.wavelength = [0.0] * 4096
        self.spectraldata = [0.0] * 4096
        self.nr_scanned = 0

        try:
            ret = av.AVS_Init(-1)
            if ret < 0:
                error_message = av_errors.get_av_error_message(ret)
                print(f"[{self.name}] Spectrometer initialization failed with error code {ret}: {error_message}")
                return
            elif ret == 0:
                print(f"[{self.name}] Spectrometer not connected. Please check the connection and try again.")
                return
            elif ret > 1:
                self._safe_shutdown(reason = f"Multiple spectrometers detected. Currently no support for this scenario. Detected {ret} devices.")
                return
            
            ret = av.AVS_UpdateUSBDevices()
            if ret == 0:
                print(f"[{self.name}] No spectrometer devices found. Please check the connection and try again.")
                return

            mylist = av.AvsIdentityType * 1
            mylist = av.AVS_GetList(1)

            self.serial_number = str(mylist[0].SerialNumber.decode("utf-8"))

            self.spectro = av.AVS_Activate(mylist[0])
            if isinstance(self.spectro, (int, float)) and self.spectro < 0:
                error_message = av_errors.get_av_error_message(self.spectro)
                self._safe_shutdown(reason = f"Failed to activate the spectrometer with code {self.spectro}: {error_message}).")
                return

            devcon = av.DeviceConfigType()
            devcon = av.AVS_GetParameter(self.spectro, 63484)

            if isinstance(devcon, (int, float)) and devcon < 0:
                error_message = av_errors.get_av_error_message(devcon)
                self._safe_shutdown(reason = 
                    f"Failed to get device configuration with code {devcon}: {error_message})."
                )
                return

            self.pixels = devcon.m_Detector_m_NrPixels

            self.get_wavelengths()

            ret = av.AVS_UseHighResAdc(self.spectro, True)

            if isinstance(ret, (int, float)) and ret < 0:
                error_message = av_errors.get_av_error_message(ret)
                self._safe_shutdown(reason = f"Failed to set high-resolution ADC mode with code {ret}: {error_message}).")
                return

            # Avaspec recommend directly setting device configuration values
            self.set_config()

            self.initialized = True

        except ConnectionError as e:
            self.serial_number = None
            print(f"[{name}] Hardware failure: {e}")

    def set_config(self):
            self.measconfig = av.MeasConfigType()
            self.measconfig.m_StartPixel = 0
            self.measconfig.m_StopPixel = self.pixels - 1
            self.measconfig.m_IntegrationTime = float(100.0)
            self.measconfig.m_IntegrationDelay = 0
            self.measconfig.m_NrAverages = int(10)
            self.measconfig.m_CorDynDark_m_Enable = 0  # nesting of types does NOT work!!
            self.measconfig.m_CorDynDark_m_ForgetPercentage = 0
            self.measconfig.m_Smoothing_m_SmoothPix = 0
            self.measconfig.m_Smoothing_m_SmoothModel = 0
            self.measconfig.m_SaturationDetection = 0
            self.measconfig.m_Trigger_m_Mode = 0
            self.measconfig.m_Trigger_m_Source = 0
            self.measconfig.m_Trigger_m_SourceType = 0
            self.measconfig.m_Control_m_StrobeControl = 0
            self.measconfig.m_Control_m_LaserDelay = 0
            self.measconfig.m_Control_m_LaserWidth = 0
            self.measconfig.m_Control_m_LaserWaveLength = 0.0
            self.measconfig.m_Control_m_StoreToRam = 0

    def get_wavelengths(self):
        """Get the wavelengths from the spectrometer and update the number of pixels."""

        x = np.array(av.AVS_GetLambda(self.spectro))

        if isinstance(x, (int, float)) and x < 0:
            error_message = av_errors.get_av_error_message(x)
            self._safe_shutdown(reason = f"Failed to get wavelengths with code {x}: {error_message}")
            return

        # Write output into the number of pixels
        self.wavelength = x[0:self.pixels]

    def start_work(self):
        while self.initialized:
            data = self.get_spectrum()
            self.data_ready.emit(self.name, 'spec', data)
        
    def get_spectrum(self):
        """Acquire single spectrum and timestamp of the spectrum acquisition"""

        self.get_wavelengths()
        x = self.wavelength

        # Create an empty array to hold the spectra data
        y_arr = np.zeros([self.pixels])
        
        ret = av.AVS_PrepareMeasure(self.spectro, self.measconfig)

        if isinstance(ret, (int, float)) and ret < 0:
                error_message = av_errors.get_av_error_message(ret)
                self._safe_shutdown(reason=f'Spectrometer failed to prepare measurement with code {ret}: {error_message}')
                return
        
        # Create a Callback function to determine when the measurement is completed.
        self.avs_cb = av.AVS_MeasureCallbackFunc(self.measure_cb)
        
        # Call the callback function to start the measurement and wait for it to complete.
        ret = av.AVS_MeasureCallback(self.spectro, self.avs_cb, int(1))

        if isinstance(ret, (int, float)) and ret < 0:
            error_message = av_errors.get_av_error_message(ret)
            self._safe_shutdown(reason=f'Spectrometer failed during measurement with code {ret}: {error_message}')
            return

        while self.nr_scanned < 1 : # wait until data has arrived
            time.sleep(0.0001)

        # Get the timestamp immediately after the measurement is complete
        timestamp = self.timestamp() 

        # Reset number of scans completed
        self.nr_scanned = 0
    
        # Copy date from the spectrometer onto the computer
        ret = av.AVS_GetScopeData(self.spectro)

        if isinstance(ret, (int, float)) and ret < 0:
            error_message = av_errors.get_av_error_message(ret)
            self._safe_shutdown(reason=f'Spectrometer failed to get scope data with code {ret}: {error_message}')
            return

        # Unpack successful retreival
        timestamp_spec, c_array = ret

        y = np.array(c_array)[0:self.pixels]

        # Avaspec spectrometers add buffer pixels on 2048 pixel spectrometers. Remove if present
        y = y[0:self.pixels]

        # Create an x and y array for the spectra data to be emitted to the controller
        spectra = np.row_stack([x, y])

        self.spectraldata = y

        # Your specific sensor logic here
        data = {'x': self.wavelength,
                'y': self.spectraldata,
                'serial_number': self.serial_number,
                'integration_time': self.measconfig.m_IntegrationTime,
                'coadds': self.measconfig.m_NrAverages,
                'timestamp': timestamp,
                'dark_correction': None,
                'nonlin_correction': None}
        
        return(data)

    def measure_cb(self,pparam1, pparam2):
        """Callback function to monitor the measurement"""

        if pparam1[0] >= 0: 
            self.nr_scanned += 1
        else:
            print(f"Measurement failed with error code: {pparam1[0]}")
            self.nr_scanned += 1 # Prevent infinite loop on failure

    def _safe_shutdown(self, reason="Unknown Error"):
        """
        Simple disconnect and cleanup of the spectrometer hardware.
        """
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")

        # Disconnect from spectrometer if issue occurs. Should work regardless of issue.
        av.AVS_Done()
            
        self.initialized = False
