"""
Created on Tue Jul 28 13:43:02 2026

@author: Matt Varnam
@email: matt(dot)varnam
"""
# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import Qt, QObject, QThread, Slot, Signal

from spytfire.analysis.so2 import SO2Analysis

# Class job is to emit incoming spectra only if it thinks analysis 
# of previous spectra is complete

class AnalysisLogger(QObject):
    data_analysis = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.threads = []
        self.worker = None
        self.add_so2_analysis()

        # Connect spectrometer source to analysis code
        if self.worker is not None:
            self.data_analysis.connect(
                    self.worker.analyse_spec,
                    type=Qt.QueuedConnection
            )

    def add_so2_analysis(self):

        worker = SO2Analysis()

        # Check that the worker has been created, and if not, skip the thread handoff
        if not worker.is_initialized:

            # Ensure cleanup of any partial objects
            worker.deleteLater() 
            return # Exit the function so no thread is started

        # Configure QThreads
        thread = QThread()
        worker.moveToThread(thread)
        
        thread.finished.connect(worker.deleteLater)

        ### CONNECT HANDLERS
        self.threads.append(thread)
        self.worker = (worker)
        
        thread.start()

    @Slot(str, str, dict)
    def handle_spec(self, name, sensor_type, data_dict):

        if self.worker is None:
            return

        # Check if the analysis worker is running
        analysing = self.worker.is_running
        initialised = self.worker.is_initialized
        
        if not analysing and initialised:
            self.data_analysis.emit(sensor_type,data_dict)

    def close_file(self):
        try:
            if self.worker is not None:
                # Terminate connections first
                self.worker._safe_shutdown(reason="User Interrupt (Ctrl+C)")

            # Tell threads to stop their event loops and wait for them to exit
            for thread in self.threads:
                thread.quit()
                thread.wait(1000)

        except RuntimeError:
            pass