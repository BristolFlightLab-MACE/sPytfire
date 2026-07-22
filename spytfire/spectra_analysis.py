"""
Created on Tue July 7 12:22:00 2026

Aim to create a worker that can operate both inside and outside spytfire.py.
It will monitor a given directory for the most recent spectra saved, then
output the SO2 quantity measured alongside pertinent UAS parameters.

First, need to make sure spectra from spectrometer sensor are output into the 
iFit format

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# =============================================================================
# Define imports
# =============================================================================

# Import the basic BasePollingWorker from the base module
from spytfire.base import BasePollingWorker

from datetime import datetime

try:
    from ifit.load_spectra import read_spectrum, average_spectra
    from ifit.spectral_analysis import Analyser
    from ifit.parameters import Parameters

except ModuleNotFoundError:
    print('iFit not found - download from University of Manchester github')

# =============================================================================
# Define the analysis worker and its attributes
# =============================================================================

class AnalysisWorker(BasePollingWorker):
    def __init__(self, name, serial_num, interval_ms = 1000):

        # Pass shared variables to BasePollingWorker
        super().__init__(name, name, serial_num, interval_ms)

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

        # Initialize an empty spectrum
        self.spectrum = None
        self.spec_type = 'iFit'

        self.analyser = Analyser(
            params,
            fit_window=[310, 320],
            stray_flag=True,
            stray_window=[298, 301],
            dark_flag=True,
            frs_path='Ref/sao2010.txt'
        )

        self.update_dark(init_dark_fnames)

    def update_dark(self, dark_fnames):
        x, dark = average_spectra(dark_fnames, self.spec_type)
        self.analyser.dark_spec = dark

    def run(self):
        try:
            self._run()
        except Exception as e:
            self._safe_shutdown(reason=e)

    def _run(self):

        # Pull analysis parameters

        # Open Save file

        # Write the analysis metaddata
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        w.write('# iFit output file\n'
                + f'# Analysis Time,{timestamp}\n'
                + f'# Fit Window Low,{self.widgetData["fit_lo"]}\n'
                + f'# Fit Window High,{self.widgetData["fit_hi"]}\n'
                + f'# Flat corr.,{self.widgetData["flat_flag"]}\n'
                + f'# Dark corr.,{self.widgetData["dark_flag"]}\n'
                + f'# Stray corr.,{self.widgetData["stray_flag"]}\n')

        # Make a list of column names
        pre_cols = [['outp_lat', 'Lat'],
                    ['outp_lon', 'Lon'],
                    ['outp_alt', 'Alt']]
        post_cols = [['outp_intlo', 'int_lo'],
                    ['outp_inthi', 'int_hi'],
                    ['outp_intav', 'int_av'],
                    ['outp_resmax', 'max_resid'],
                    ['outp_resstd', 'std_resid'],
                    ['outp_fitqual', 'fit_quality']]

        # Add pre columns
        cols = ['File', 'Number', 'Time']

        # Read in the spectrum
        fname = spec_fnames[loop]
        x, y, metadata, read_err = read_spectrum(fname, spec_type,
                                                    wl_calib_file)
        
        # Fit the spectrum using iFit
        fit_result = self.analyser.fit_spectrum(
            spectrum=[x, y],
            update_params=update_flag,
            resid_limit  =resid_limit,
            resid_type   =resid_type,
            sat_limit    =sat_limit,
            int_limit    =int_limit,
            calc_od      =graph_p,
            interp_method=interp_meth,
            prefit_shift =prefit_shift
        )