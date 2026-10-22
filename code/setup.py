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
