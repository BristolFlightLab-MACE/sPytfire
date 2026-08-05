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
from rclpy.node import Node

from std_msgs.msg import String


class MinimalPublisher(Node):

    def __init__(self):
        super().__init__('minimal_publisher')
        self.publisher_ = self.create_publisher(String, 'topic', 10)
        timer_period = 0.5  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = 'Hello World: %d' % self.i
        self.publisher_.publish(msg)
        self.get_logger().info('Publishing: "%s"' % msg.data)
        self.i += 1

def main(args=None):
    rclpy.init(args=args)

    minimal_publisher = MinimalPublisher()

    rclpy.spin(minimal_publisher)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    minimal_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()