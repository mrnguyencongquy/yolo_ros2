from setuptools import find_packages, setup

package_name = "robot_ai"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/robot_ai.launch.py"]),
    ],
    install_requires=["setuptools"],
    tests_require=["pytest"],
    zip_safe=True,
    maintainer="vizo",
    maintainer_email="dev3@vizo.co.jp",
    description="Grass detection ROS2 nodes",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "sample_publisher = robot_ai.sample_publisher:main",
            "yolo_bridge = robot_ai.yolo_bridge:main",
        ],
    },
)
