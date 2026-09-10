from setuptools import find_packages, setup

package_name = "openipc_cinewhoop_demo"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/demo.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="phage",
    maintainer_email="phage@example.invalid",
    description="Python ROS 2 demo nodes for the OpenIPC cinewhoop simulation.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "obstacle_monitor = openipc_cinewhoop_demo.obstacle_monitor:main",
            "range_adapter = openipc_cinewhoop_demo.range_adapter:main",
            "simple_indoor_autonomy = openipc_cinewhoop_demo.simple_indoor_autonomy:main",
            "trajectory_publisher = openipc_cinewhoop_demo.trajectory_publisher:main",
        ],
    },
)
