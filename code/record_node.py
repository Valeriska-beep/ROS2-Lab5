import csv
import os
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class RecordNode(Node):
    def __init__(self):
        super().__init__('record_node')

        self.subscription = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_vel_callback,
            10
        )

        self.file_path = os.path.expanduser('~/ros2_ws/scenario.csv')
        self.start_time = None
        self.last_command = None

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.file = open(self.file_path, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['time', 'linear_x', 'angular_z'])
        self.file.flush()

        self.get_logger().info(f'Record Node запущено. Запис ведеться у: {self.file_path}')

    def cmd_vel_callback(self, msg):
        current_time = time.monotonic()
        linear_x = round(msg.linear.x, 2)
        angular_z = round(msg.angular.z, 2)
        command = (linear_x, angular_z)

        # Фільтрація: ігноруємо дубльовані команди поспіль
        if self.last_command == command:
            return

        if self.start_time is None:
            self.start_time = current_time

        rel_time = round(current_time - self.start_time, 2)
        self.last_command = command

        self.writer.writerow([rel_time, linear_x, angular_z])
        self.file.flush()

        self.get_logger().info(
            f'Записано: t={rel_time} с | linear_x={linear_x} | angular_z={angular_z}'
        )

    def destroy_node(self):
        if hasattr(self, 'file') and not self.file.closed:
            self.file.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = RecordNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
