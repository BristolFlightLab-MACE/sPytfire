# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 13:00:08 2026

@author: Matt Varnam
@email: matt(dot)varnam(at)bristol(dot)ac(dot)uk
"""
# Import pyside6 to create the process for reading data in to an application
from PySide6.QtCore import QObject, Signal, Slot, QCoreApplication, Qt

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BaseWorker

# Import python mavlink
import pymavlink.mavutil as mavutil

class MavlinkWorker(BaseWorker):
    #data_ready = Signal(str, dict)
    recording_trigger = Signal(bool)
    uas_time_updated  = Signal('qint64')

    def __init__(self, connection_str, channel_num = 11, name="MAVLink"):
        super().__init__(name)
        
        # Identify the name of the MAVLINK channel from the input number
        channel_dict = {i: f'chan{i}_raw' for i in range(1, 19)}
        
        try:
            channel_name = channel_dict[channel_num]
        except KeyError:
            raise ValueError('Incorrect channel chosen')
        
        self.connection_str = connection_str
        self.channel_name = channel_name
        self.name = name
        self.recording = True
        self.initialized = True

    def start_work(self):
        try:
            # 1. Initialize connection
            self.mav_conn = mavutil.mavlink_connection(self.connection_str,baud=57600)
            print(f"MAVLink listening on {self.connection_str}")

            # 2. Continuous Read Loop
            while self.initialized:
                # blocking=True with a timeout lets the CPU rest 
                # without using Qt Timer.
                msg = self.mav_conn.recv_match(type=['SYSTEM_TIME','RC_CHANNELS','TIMESYNC'],
                                             blocking=True, timeout=0.1)
                
                if msg:
                    self.handle_message(msg)

        except Exception as e:
            print(f"[-] MAVLink Error: {e}")
            
        finally:
            # Safely close only if self.parent was successfully initialized
            if hasattr(self, 'mav_conn') and self.mav_conn is not None:
                try:
                    self.mav_conn.close()
                except Exception as close_error:
                    print(f"[-] Error closing MAVLink connection: {close_error}")

    def handle_message(self, msg):
        """Filter and emit only the data required. Included placeholders."""
        m_type = msg.get_type()
        
        # Readout the MAVLINK messagetype and match it to message types of interest
        match m_type:
            #case 'HEARTBEAT':                                    #msg_type   0
            #    pass
            case 'SYSTEM_TIME':                                   #msg_type   2
                self.uas_time_updated.emit(msg.time_unix_usec)
            case 'GLOBAL_POSITION_INT':
                msg.lat
                msg.lon
                msg.alt
            case 'RC_CHANNELS':                                   #msg_type  35
                channel_value = getattr(msg, self.channel_name, 1500)
                if channel_value == 0:
                    return
                
                elif channel_value > 1800 and not self.recording:
                    self.set_recording_state(True, "Payload recording Started")
                                             
                elif channel_value < 1200 and self.recording:
                    self.set_recording_state(False, "Payload recording Stopped")                          
            #case 'TIMESYNC':                                      #msg_type 111
            #    pass
            case 'HIL_STATE_QUATERNION':                           #msg_type 115
                msg.true_airspeed

    def set_recording_state(self, state, status_text):
            """Helper to deduplicate statustext packet transmissions."""
            self.recording = state
            self.recording_trigger.emit(state)
            if self.parent:
                self.parent.mav.statustext_send(
                    mavutil.mavlink.MAV_SEVERITY_INFO,
                    status_text.encode('utf-8')
            )
    