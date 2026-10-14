from setuptools import find_packages, setup

package_name = "openipc_vrx"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/vrx_bridge.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="phage",
    maintainer_email="phage@example.invalid",
    description="Ground bridge from the Walksnail VRX Pro over USB into ROS 2.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "vrx_bridge = openipc_vrx.bridge:main",
            "detector = openipc_vrx.detector_node:main",
            "web_view = openipc_vrx.web_view:main",
        ],
    },
)
