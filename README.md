# Лабораторна робота №5
## Запис і відтворення сценаріїв руху робота в ROS 2

Підготовка середовища та перевірка топіка /cmd_vel
Активуємо базове середовище ROS 2 Humble та робочий простір:

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws
source install/setup.bash
```

Перевіряємо наявність необхідних базових пакетів:

```bash
ros2 pkg list | grep -E 'motion_control|robot_gui'
```

Запускаємо вузли керування роботом і графічного інтерфейсу у двох окремих терміналах:

```bash
# Термінал 1:
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run motion_control motion_node

# Термінал 2:
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run robot_gui gui_node

# Термінал 3 (перевіряємо активні топіки):
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 topic list
```


Створюємо пакет типу ament_python із необхідними залежностями rclpy та geometry_msgs:

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws/src
ros2 pkg create --build-type ament_python motion_playback_pkg --dependencies rclpy geometry_msgs
```

Реалізація ноди запису (record_node.py)
Нода підписується на топік /cmd_vel (тип повідомлення geometry_msgs/msg/Twist). Для уникнення надлишкових записів під час утримання кнопок інтерфейсу реалізовано фільтрацію дублікатів. Часові мітки формуються відносно старту через time.monotonic(), а буфер негайно скидається на диск (flush()).

Шлях до файлу:

```bash
nano ~/ros2_ws/src/motion_playback_pkg/motion_playback_pkg/record_node.py
```

```Python
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
```

Реалізація ноди відтворення (playback_node.py)
Нода зчитує файл scenario.csv та публікує команди у топік /cmd_vel з використанням періодичного таймера (інтервал опитування 20 мс) без блокування основного потоку. Після публікації останньої команди вузол надсилає безпечну команду зупинки зі швидкістю 0.0.

Шлях до файлу: 

```bash
nano ~/ros2_ws/src/motion_playback_pkg/motion_playback_pkg/playback_node.py    
```

```Python
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
```

Конфігурація setup.py та збірка пакета, додано точки входу для обох скриптів:
У файлі 
```bash
nano ~/ros2_ws/src/motion_playback_pkg/setup.py 
```

```Python
from setuptools import find_packages, setup

package_name = 'motion_playback_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='valeri',
    maintainer_email='valeri@todo.todo',
    description='Record and playback robot motion scenarios',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'record_node = motion_playback_pkg.record_node:main',
            'playback_node = motion_playback_pkg.playback_node:main',
        ],
    },
)
```

Збираємо робоче середовище:

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select motion_playback_pkg
source install/setup.bash
ros2 pkg executables motion_playback_pkg
```

Запис сценарію руху
Для запису послідовно запустили вузли в окремих терміналах:

Термінал 1 — запуск motion_node

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run motion_control motion_node
```

Термінал 2 — запуск запису

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run motion_playback_pkg record_node
```

Термінал 3 — запуск графічного інтерфейсу

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run robot_gui gui_node
```

Дії під час тесту: у GUI послідовно натиснуто клавіші «Праворуч», «Вперед», «Ліворуч», «Назад», «Стоп» (завершальна «Стоп» потрібна, щоб останній рух мав реальну тривалість при відтворенні). Вузол record_node відфільтрував спам однакових повідомлень і зафіксував зміну координат із мітками часу.

Перевіряємо збережений сценарій у терміналі:

```bash
cat ~/ros2_ws/scenario.csv
```

Відтворення сценарію
Залишаємо активними Термінал 1 (motion_node) та Термінал 3 (robot_gui). У новому терміналі запускаємо ноду відтворення:

Термінал 4 — запуск відтворення

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run motion_playback_pkg playback_node
```

Моніторимо потік команд у реальному часі:

```bash
ros2 topic list
ros2 topic echo /cmd_vel
```

Вузол playback_node успішно зчитав команди з CSV та опублікував їх у /cmd_vel із точним дотриманням вихідних часових пауз, після чого відправив фінальну команду зупинки. Статуси руху коректно відтворювалися у вікні robot_gui.



# Запуск програми
Збірка робочого простору

```bash
cd ~/ros2_ws
colcon build --packages-select motion_playback_pkg
source install/setup.bash
# Перевіряємо, що обидва виконувані файли зареєстровані
ros2 pkg executables motion_playback_pkg
```


Термінал 1: Вузол обробки руху (motion_node)
Цей вузол виступає виконавчим модулем: приймає команди швидкості й виводить поточний стан. 

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run motion_control motion_node
```

Термінал 2: Графічний інтерфейс

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run robot_gui gui_node
```

Термінал 3: Вузол запису (record_node)
Він підключається до шини /cmd_vel і очікує дій оператора.   

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run motion_playback_pkg record_node
```

Перевірка створеного CSV

```bash
cd ~/ros2_ws
ls -l scenario.csv
cat scenario.csv
```

Згенерований сценарій у форматі CSV: колонка часу від старту, лінійна швидкість linear_x та кутова angular_z. 
Останнім рядком записана швидкість 0.0, 0.0 для безпечної зупинки.  


Терміналі 4: Автоматичне відтворення сценарію (Playback)

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run motion_playback_pkg playback_node
```

Додатковий моніторинг (опціонально у Терміналі 4): Перевірка перехоплення шини

```bash
ros2 topic echo /cmd_vel
```
