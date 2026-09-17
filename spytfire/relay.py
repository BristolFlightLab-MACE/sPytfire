# -*- coding: utf-8 -*-
"""
Created on Wed Sep 16 16:28:11 2026

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================
# Import the basic BaseWorker from the base module to apply to Apogee sensors
import os
if os.name == "nt":
    frequency_Hz = 100000
    os.environ["BLINKA_MCP2221"] = "1"
    os.environ["BLINKA_MCP2221_I2C_FREQUENCY"] = str(frequency_Hz)

from PySide6.QtCore import QObject

import board
import digitalio

# =============================================================================

class RelayControl(QObject):
    def __init__(self, pin = None):
        super().__init__()

        if pin is None:
            pin = board.D25
        
        self.relay = digitalio.DigitalInOut(pin)
        self.relay.direction = digitalio.Direction.OUTPUT
        self.initialized = True

    def relay_on(self):
        self.relay.value = True

    def relay_off(self):
        self.relay.value = False

    def relay_toggle(self):
        self.relay.value = not self.relay.value

    def close(self, reason="Unknown Error"):
        self.relay_off()
        self.initialized = False