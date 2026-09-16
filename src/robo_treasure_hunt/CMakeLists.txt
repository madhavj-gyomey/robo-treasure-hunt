cmake_minimum_required(VERSION 3.0.2)
project(robo_treasure_hunt)

find_package(catkin REQUIRED COMPONENTS
  geometry_msgs
  nav_msgs
  roscpp
  rospy
  sensor_msgs
  std_msgs
  visualization_msgs
  gazebo_msgs
  tf
)

catkin_package(
  CATKIN_DEPENDS
    geometry_msgs
    nav_msgs
    roscpp
    rospy
    sensor_msgs
    std_msgs
    visualization_msgs
    gazebo_msgs
    tf
)

include_directories(
  ${catkin_INCLUDE_DIRS}
)

catkin_install_python(PROGRAMS
  scripts/player_controller.py
  scripts/game_manager.py
  scripts/treasure_detector.py
  scripts/security_detector.py
  scripts/game_hud.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
