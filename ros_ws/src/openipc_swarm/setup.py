from setuptools import find_packages, setup

package_name = "openipc_swarm"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="phage",
    maintainer_email="phage@example.invalid",
    description="Coordinator layer for the three-drone mapping task in spec/roj.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "coordinator = openipc_swarm.coordinator:main",
        ],
    },
)
