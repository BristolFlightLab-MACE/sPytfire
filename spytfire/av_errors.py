"""
Created on Mon Jul 06 15:58:00 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# =============================================================================
# Define a function to return the error message of each Avaspec error code
# =============================================================================

# Error codes for the spectrometer
def get_av_error_message(error_code):
    """
    Returns a human-readable error message for a given Avantes error code.

    Parameters
    ----------
    error_code : int
        The error code returned by the Avantes spectrometer functions.

    Returns
    -------
    str
        A human-readable error message corresponding to the error code.
    """
    error_messages = {-1:   'Function called with invalid parameter',
                      -2:   'Function called to use 16bit ADC mode, with 14bit ADC hardware',
                      -3:   'Opening communication failed or time-out during communication occurred',
                      -4:   'AvsHandle is unknown in the DLL',
                      -5:   'Function is called while result of previous function is not received yet',
                      -6:   'No answer received from device',
                      -7:   'Reserved',
                      -8:   'No measurement data is received at the point AVS_GetScopeData is called',
                      -9:   'Allocated buffer size too small',
                      -10:  'Measurement preparation failed because pixel range is invalid',
                      -11:  'Measurement preparation failed because integration time is invalid for selected sensor',
                      -12:  'Measurement preparation failed because of invalid combination of parameters (e.g. integration time > 600 seconds or averages > 5000)',
                      -13:  'Reserved',
                      -14:  'Measurement preparation failed because no measurement buffers are available',
                      -15:  'Unknown error reason received from spectrometer',
                      -16:  'Error in communication occurred',
                      -17:  'No more spectra available in RAM, all read or measurement not started yet',
                      -18:  'DLL version information can not be retrieved',
                      -19:  'Memory allocation error in the DLL',
                      -20:  'Function called before AVS_Init is called',
                      -21:  'Function failed because AS5216 is in wrong state (e.g. AVS_StartMeasurement while measurement is pending)',
                      -100: 'NrOfPixel in Device data incorrect',
                      -101: 'Gain Setting Out of Range',
                      -102: 'Offset Setting Out of Range',
                      -110: 'Use of Saturation Detection Level 2 is not compatible with the Averaging function',
                      -111: 'Use of Averaging is not compatible with the StoreToRam function',
                      -112: 'Use of the Synchronize setting is not compatible with the StoreToRam function',
                      -113: 'Use of Level Triggering is not compatible with the StoreToRam function',
                      -114: 'Use of Saturation Detection Level 2 Parameter is not compatible with the StoreToRam function',
                      -115: 'The StoreToRam function is only supported with firmware version 0.20.0.0 or later',
                      -116: 'Dynamic Dark Correction not supported',
                      -117: 'Use of AVS_SetSensitivityMode() not supported by detector type',
                      -121: 'Use of AVS_SetSensitivityMode() not supported by firmware version',
                      -122: 'Use of AVS_SetSensitivityMode() not supported by FPGA version',
                      -140: 'Spectrometer was not calibrated for stray light correction',
                      -141: 'Incorrect start pixel found in EEPROM',
                      -142: 'Incorrect end pixel found in EEPROM',
                      -143: 'Incorrect start or end pixel found in EEPROM',
                      -144: 'Factor should be in range 0.0 -- 4.0'}
    
    # Safe Lookup of Avaspec error code in the dictionary
    error_string = error_messages.get(error_code, "Unknown error code")

    return error_string

# =============================================================================
# Create a short demonstration of the usage of the Avaspec error codes
# =============================================================================

# Short code demonstrating the error code usage
if __name__ == "__main__":
    # Example usage of the get_av_error_message function
    error_code = -3  # Example error code
    error_message = get_av_error_message(error_code)
    print(f"Error Code: {error_code}, Message: {error_message}")