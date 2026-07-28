"""
Created on Tue July 7 12:22:00 2026

There are architectural issues with having analysis as a Logger. It needs to be 
moved back to a worker to avoid potential freezing of the main thread.

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# =============================================================================
# Define imports
# =============================================================================

# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import QObject, Slot, Signal

# datetime for interpreting and formatting the time and date
from datetime import datetime

# Load other libraries
from pathlib import Path
import os
import time
import numpy as np

try:
    from ifit.load_spectra import read_spectrum, average_spectra
    from ifit.spectral_analysis import Analyser
    from ifit.parameters import Parameters

except ModuleNotFoundError:
    print('iFit not found - download from University of Manchester github')

# =============================================================================
# Define the analysis worker and its attributes
# =============================================================================

dummy_dir = (r'C:\Users\cx25261\Documents\projects\MACE\coding\iFit\Results')

dummy_dnames = [dummy_dir + '/dark/' + file for file in os.listdir(dummy_dir + '/dark')]

class SO2Analysis(QObject):
    data_ready = Signal(str, str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.initialized = False
        # Create iFit parameter dictionary
        self._create_parameters()

        # Initialize an empty spectrum
        self.spectrum = None
        self.spec_type = 'iFit'

        # Initialize an analyser class for iFit analysis
        self.analyser = Analyser(
            self.params,
            fit_window=[310, 320],
            stray_flag=True,
            stray_window=[298, 301],
            dark_flag=True,
            frs_path='Ref/sao2010.txt'
        )

        self.resid_limit = 6
        self.int_limit = [0,65000]
        self.calc_od_key = ['O3']

        self.dark_fnames = dummy_dnames
        self.update_dark(dummy_dnames)

        # Create toggle to prevent multiple fitting iterations running at the 
        # same time
        self.running = False
        self.initialized = True

    @property
    def is_initialized(self):
        """Safe read-only access for the main thread."""
        return self.initialized

    @property
    def is_running(self):
        """Safe read-only access for the main thread."""
        return self.running

    def _create_parameters(self):

        # Create parameter dictionary
        params = Parameters()

        # Add the gases
        params.add('SO2',  value=1.0e16, vary=True, xpath='Ref/SO2_295K.txt')
        params.add('O3',   value=1.0e19, vary=True, xpath='Ref/O3_243K.txt')
        params.add('Ring', value=0.1,    vary=True, xpath='Ref/Ring.txt')

        # Add background polynomial parameters
        params.add('bg_poly0', value=0.0, vary=True)
        params.add('bg_poly1', value=0.0, vary=True)
        params.add('bg_poly2', value=0.0, vary=True)
        params.add('bg_poly3', value=1.0, vary=True)

        # Add intensity offset parameters
        params.add('offset0', value=0.0, vary=False)

        # Add wavelength stretch and shift parameters
        params.add('shift0', value=0.0, vary=True)
        params.add('shift1', value=0.1, vary=True)

        # Add ILS parameters
        params.add('fwem', value=0.6, vary=True)
        params.add('k',    value=2.0, vary=False)
        params.add('a_w',  value=0.0, vary=False)
        params.add('a_k',  value=0.0, vary=False)

        self.params = params
        
    def update_dark(self, dark_fnames):

        x, dark = average_spectra(dark_fnames, self.spec_type)
        self.analyser.dark_spec = dark

    def timestamp(self):
        """Returns the current time in nanoseconds from the connected."""
        return time.monotonic_ns()

    @Slot(dict)
    def analyse_spec(self, data_dict):

        self.running = True

        # If analysis code not already running then:
        try:
            self.data_dict = data_dict
            self.analyse_spectrum()

        except Exception as e:
            print(f'Error during analysis: {e}')

        finally:
            self.running = False

    def analyse_spectrum(self):

        wav  = self.data_dict['x']
        self.spec = self.data_dict['y']
                
        # Fit the spectrum using iFit
        fit_result = self.analyser.fit_spectrum(
            spectrum = [wav, self.spec],
            resid_limit = self.resid_limit, int_limit = self.int_limit,
            calc_od=['SO2']
        )

        self.nerr = fit_result.nerr

        self.check_output(fit_result)

        out_params = {}
        key_list = [key for key in self.params if self.params[key].vary]

        for i,key in enumerate(key_list):

            #Only keep SO2 for now
            if key in ['SO2','O3']:
                out_params[key] = fit_result.popt[i]

        data_output = {'timestamp': self.timestamp(),
                       'so2': out_params['SO2'],
                       'o3' : out_params['O3']
        }
        self.data_ready.emit('iFit', 'so2', data_output)

    def check_output(self,fit_result):

        if self.nerr:
            # Check the fit quality
            if self.resid_limit is not None and max(abs(fit_result.resid)) > self.resid_limit:
                print('High residual detected')

            # Check for spectrum light levels
            if self.int_limit is not None:

                # Check for low intensity
                if min(self.spec) <= self.int_limit[0]:
                    print('Low intensity detected')

                # Check for high intensity
                elif max(self.spec) >= self.int_limit[1]:
                    print('High intensity detected')

            # Calculate optical depth spectra
            for par in self.calc_od_key:
                if par in self.params:
                    meas_od, synth_od = fit_result.calc_od(par, self.analyser)
                    # Check for nans in OD
                    if np.isnan(meas_od).any() or np.isnan(synth_od).any():
                        print('Bad optical depth detected')

        # If not then return nans
        else:
            print('Fit failed!')
            self.fit = np.full(len(self.spec), np.nan)
            fit_result.resid = np.full(len(self.spec), np.nan)
            self.resid_max = np.nan
            self.resid_std = np.nan
            for par in self.calc_od_key:
                if par in self.params:
                    self.meas_od[par] = np.full(len(self.spec), np.nan)
                    self.synth_od[par] = np.full(len(self.spec), np.nan)

    def _safe_shutdown(self,reason="Unknown Error"):   
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")
        
        self.initialized = False