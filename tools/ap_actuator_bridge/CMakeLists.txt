cmake_minimum_required(VERSION 3.16)
project(ap_actuator_bridge CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(gz-transport13 REQUIRED)
find_package(gz-msgs10 REQUIRED)

add_executable(ap_actuator_bridge main.cc)
target_link_libraries(ap_actuator_bridge
  PRIVATE gz-transport13::core gz-msgs10::core)

install(TARGETS ap_actuator_bridge RUNTIME DESTINATION bin)
