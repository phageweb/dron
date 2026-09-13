cmake_minimum_required(VERSION 3.10)
project(openipc_cinewhoop_gazebo)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch models models_pavo20 worlds
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
