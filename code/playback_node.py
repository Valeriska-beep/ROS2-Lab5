import csv
import os
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class PlaybackNode(Node):
    def __init__(self):
        super().__init__('playback_node')

        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.file_path = os.path.expanduser('~/ros2_ws/scenario.csv')
        self.commands = []
        self.start_time = None
        self.next_index = 0
        self.finished = False

        self.get_logger().info('Очікування підключення до топіка /cmd_vel...')
        self.timer = self.create_timer(0.5, self.start_playback)

    def start_playback(self):
        self.timer.cancel()

        if not os.path.exists(self.file_path):
            self.get_logger().error(f'Файл {self.file_path} не знайдено!')
            return

        with open(self.file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 3:
                    try:
                        t = float(row[0].strip())
                        lx = float(row[1].strip())
                        az = float(row[2].strip())
                        self.commands.append((t, lx, az))
                    except ValueError:
                        continue

        if not self.commands:
            self.get_logger().warn('Файл сценарію порожній!')
            return

        self.get_logger().info(f'Початок відтворення: {len(self.commands)} команд.')
        self.start_time = time.monotonic()
        self.timer = self.create_timer(0.02, self.playback_loop)

    def playback_loop(self):
        if self.finished:
            return

        current_elapsed = time.monotonic() - self.start_time

        while self.next_index < len(self.commands):
            target_time, linear_x, angular_z = self.commands[self.next_index]

            if current_elapsed >= target_time:
                msg = Twist()
                msg.linear.x = linear_x
                msg.angular.z = angular_z
                self.publisher.publish(msg)

                self.get_logger().info(
                    f'Відтворено [t={target_time:.2f} с]: linear.x={linear_x}, angular.z={angular_z}'
                )
                self.next_index += 1
            else:
                break

        # Безпечна зупинка після виконання всіх пунктів сценарію
        if self.next_index >= len(self.commands):
            self.finished = True
            self.timer.cancel()

            stop_msg = Twist()
            stop_msg.linear.x = 0.0
            stop_msg.angular.z = 0.0
            self.publisher.publish(stop_msg)

            self.get_logger().info('Сценарій завершено. Команду зупинки надіслано.')

def main(args=None):
    rclpy.init(args=args)
    node = PlaybackNode()
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
