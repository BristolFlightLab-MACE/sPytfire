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
    def __init__(self, multiplex=False):
        self.multiplex = multiplex
        
        try:
            self.i2c = board.I2C()

            if self.multiplex:
                self.bus = adafruit_tca9548a.PCA9546A(self.i2c)
            else:
                self.bus = self.i2c

        except:
            self.bus = None

    def get_channel(self, address):
        if address is list or tuple and self.multiplex:
            channel, _ = address
            return self.bus[channel]
        else:
            return self.bus        

    def close(self):
        self.bus = None
        self.i2c.deinit()
        self.i2c = None
        