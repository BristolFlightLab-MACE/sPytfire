"""
Created on Tue Mar 31 12:04:52 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# Import Signal from PySide to allow the workers to send signals
from PySide6.QtCore import QObject, Slot

import numpy as np

# =========================================================================
#  Logger to output data to console for testing
# =========================================================================
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
    @Slot(str, str, dict)
    def handle_data(self, name, sensor_type, data_dict):
        #pass
        print(name)

        for key in data_dict:
            if key != 'y':
                print(f"{key}:{data_dict[key]:.6f}")
            else:
                print([np.array2string(v, precision=1, floatmode='fixed') if isinstance(v, np.ndarray) else str(v) 
                       for v in data_dict[key]])

    # Create a dummy slot to ignore the arrival of data from the spectrometer            
    @Slot(str, str, dict)
    def handle_spec(self, name, sensor_type, data_dict):
        pass
