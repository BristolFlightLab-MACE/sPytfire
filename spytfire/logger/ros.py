try:
    import rclpy.node
    import mace_sensor_interfaces.msg as mace_msgs
except ImportError:
    print("Wraning: Error importing ROS modules. ROS transport not available")

class RosLogger(QObject):
    """Sends emitter data over ROS."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Setup ROS connection
        rclpy.init()
        self.node = rclpy.node.Node("mace_sensors")

        # Setup ROS publishers
        self.AdaFruit_pub = self.node.create_publisher(mace_msgs.AdaFruit, '/mace_sensors/AdaFruit', 10)
        self.BME280_pub = self.node.create_publisher(mace_msgs.BME280, '/mace_sensors/BME280', 10)
        self.SL510_1729_pub = self.node.create_publisher(mace_msgs.ApogeeLx, '/mace_sensors/SL510_1729', 10)
        self.SL610_1463_pub = self.node.create_publisher(mace_msgs.ApogeeLx, '/mace_sensors/SL610_1463', 10)
        self.SP510_3985_pub = self.node.create_publisher(mace_msgs.ApogeeS, '/mace_sensors/SP510_3985', 10)
        self.SPN1_pub = self.node.create_publisher(mace_msgs.SPN1, '/mace_sensors/SPN1', 10)
        self.OPC_N3_pub = self.node.create_publisher(mace_msgs.OPC, '/mace_sensors/OPC_N3', 10)
        self.Ex_volt_pub = self.node.create_publisher(mace_msgs.ExVoltage, '/mace_sensors/Ex_volt', 10)

    @Slot(str)
    def handle_time(self, uas_time):
        pass
        #print(f"[Time] {uas_time}")

    @Slot(str, dict)
    def handle_data(self, name, data_dict):
        match name:
            case 'AdaFruit':
                self.AdaFruit_pub.publish(mace_msgs.AdaFruit(*data_dict))
            case 'BME280':
                self.BME280_pub.publish(mace_msgs.BME280(*data_dict))
            case 'SL510_1729':
                self.SL510_1729_pub.publish(mace_msgs.ApogeeLx(*data_dict))
            case 'SL610_1463':
                self.SL610_1463_pub.publish(mace_msgs.ApogeeLx(*data_dict))
            case 'SP510_3985':
                self.SP510_3985_pub.publish(mace_msgs.ApogeeS(*data_dict))
            case 'SPN1':
                self.SPN1_pub.publish(mace_msgs.SPN1(*data_dict))
            case 'OPC_N3':
                self.OPC_N3_pub.publish(mace_msgs.OPC(*data_dict))
            case 'Ex_volt':
                self.Ex_volt_pub.publish(mace_msgs.ExVoltage(*data_dict))
