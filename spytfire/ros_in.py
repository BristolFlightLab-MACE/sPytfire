# -*- coding: utf-8 -*-
"""
Created on Tue Mar 31 13:00:08 2026

@author: Matt Varnam
@email: matt(dot)varnam
"""
# =============================================================================
# Define imports
# =============================================================================

# Import pyside6 to create the process for reading data in to an application
from PySide6.QtCore import QObject, Signal, Slot, QCoreApplication, Qt

# Import the basic BaseWorker from the base module to apply to Apogee sensors
from spytfire.base import BaseWorker

# Import python mavlink
import pymavlink.mavutil as mavutil

# =============================================================================
# Create new BaseWorker for monitoring the MAVlink connection
# =============================================================================

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from std_msgs.msg import String

class EthWorker(Node, BaseWorker):

    def __init__(self, name):
        Node.__init__('minimal_subscriber')
        BaseWorker.__init__(name,serial_num=None,address=None,interval_ms=None)

        try:
            with rclpy.init(args=None):
                self.start_ros()
                rclpy.spin(self)

        except (KeyboardInterrupt, ExternalShutdownException):
            pass

        self.recording = True
        self.initialized = True
        
    def start_ros(self):
        self.subscription = self.create_subscription(
            String,
            'topic',
            self.handle_message,
            10)
        self.subscription  # prevent unused variable warning

    def handle_message(self, msg):
        """Filter and emit only the data required. Included placeholders."""
        m_type = msg.get_type()
        
        # Readout the MAVLINK messagetype and match it to message types of interest
        match m_type:
            #case 'HEARTBEAT':                                    #msg_type   0
            #    pass
            case 'SYSTEM_TIME':                                   #msg_type   2
                self.uas_time_updated.emit(msg.time_unix_usec)
            case 'GLOBAL_POSITION_INT':                           #msg_type  33
                data_dict = {'lat': msg.lat,
                             'lon': msg.lon,
                             'alt': msg.alt,
                             'vehicle_timestamp': msg.time_boot_ms,
                             'timestamp': self.timestamp()}
                self.data_ready.emit('GPS', 'gps', data_dict)
            case 'ATTITUDE':                                      #msg_type  30
                data_dict = {'roll': msg.roll,
                             'pitch': msg.pitch,
                             'yaw': msg.yaw,
                             'vehicle_timestamp': msg.time_boot_ms,
                             'timestamp': self.timestamp()}
                self.data_ready.emit('IMU', 'attitude', data_dict)
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
            #case 'HIL_STATE_QUATERNION':                           #msg_type 115
            #    msg.true_airspeed

    def set_recording_state(self, state, status_text):
            """Helper to deduplicate statustext packet transmissions."""
            self.recording = state
            self.recording_trigger.emit(state)
            if self.parent:
                self.parent.mav.statustext_send(
                    mavutil.mavlink.MAV_SEVERITY_INFO,
                    status_text.encode('utf-8')
            )
                
    def _safe_shutdown(self, reason="Unknown Error"):
        if reason != ("User Interrupt (Ctrl+C)"):
            print(f"\n[CRITICAL ERROR] Initiating Safe Shutdown for {self.name}!")
            print(f"Reason: {reason}")
            
        if hasattr(self, 'mav_conn') and self.mav_conn is not None:
            try:
                self.mav_conn.close()
            except Exception as close_error:
                print(f"[-] Error closing MAVLink connection: {close_error}")
            
        self.initialized = False