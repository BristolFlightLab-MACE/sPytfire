"""
Created on Tue July 7 12:22:00 2026

Aim to create a worker that can operate both inside and outside spytfire.py.
It will receive the filenames of spectra to analyse, then save results to a
specified directory.

First, need to make sure spectra from spectrometer sensor are output into the 
iFit format

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# =============================================================================
# Define imports
# =============================================================================

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BaseWorker

# =============================================================================
# Define the analysis worker and its attributes
# =============================================================================

class AnalysisWorker(BaseWorker):
    def __init__(self, name, outfile):

        # Pass shared variables to BaseWorker
        super().__init__(name)
        self.spectrum = None

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
        
        # Fit the spectrum
        fit_result = self.analyser.fit_spectrum(
            spectrum=[x, y],
            update_params=update_flag,
            resid_limit=resid_limit,
            resid_type=resid_type,
            sat_limit=sat_limit,
            int_limit=int_limit,
            calc_od=graph_p,
            interp_method=interp_meth,
            prefit_shift=prefit_shift
        )