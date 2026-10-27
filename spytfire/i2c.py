# -*- coding: utf-8 -*-
"""
Created on Thu Sep 17 14:05:04 2026

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================

import os
if os.name == "nt":
    frequency_Hz = 100000
    os.environ["BLINKA_MCP2221"] = "1"
    os.environ["BLINKA_MCP2221_I2C_FREQUENCY"] = str(frequency_Hz)

# deferred to allow MCP2221 to be initialized before board.I2C() is called on Windows
import board

# Import library for managing the I2C multiplexer if present
import adafruit_tca9548a

# =============================================================================

class I2CManager:
    def __init__(self, multiplex=False, type='board',i2cline=None):
        self.initialized = False
        self.multiplex = multiplex

        if type == 'board':
            self.setup_i2c_board()
        elif type == 'smbus2':
            self.setup_i2c_smbus2(i2cline)

        self.initialized = True

    @property
    def is_initialized(self):
        """Safe read-only access for the main thread."""
        return self.initialized

    def setup_i2c_board(self):
        try:
            self.i2c = board.I2C()

            if self.multiplex:
                self.bus = adafruit_tca9548a.PCA9546A(self.i2c)
                print(f'Multiplexer detected on I2C bus {self.i2c}')
            else:
                self.bus = self.i2c

        except Exception as exc:
            print(f'Exception encountered {exc}')
            self.bus = None

    def setup_i2c_smbus2(self,i2cline=2):
        import smbus2

        try:
            self.i2c = smbus2.SMBus(i2cline)
            self.bus = self.i2c

        except Exception as exc:
            print(f'Exception encountered {exc}')
            self.bus = None

    def get_channel(self, address):
        if address is None:
            return None
        elif address is list or tuple and self.multiplex:
            channel, _ = address
            return self.bus[channel]
        else:
            return self.bus        

    def close(self):
        self.bus = None
        self.i2c.deinit()
        self.i2c = None
        self.initialized = False