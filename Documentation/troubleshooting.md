# Robo Treasure Hunt — Troubleshooting & Setup Guide

## 1. Graphics & X11 Display in WSL
The PyQt5 HUD and Gazebo GUI require an active X11 server connection.

### WSLg (Windows 11)
Windows 11 provides integrated WSLg. Verify DISPLAY:
```bash
echo $DISPLAY  # Expected: :0
```

### VcXsrv / Xming (Windows 10)
If using an external X server on Windows 10:
```bash
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0
export LIBGL_ALWAYS_INDIRECT=0
```

## 2. Gazebo Model & Xacro Resolution
If Gazebo fails to spawn the TurtleBot3 URDF:
```bash
# Verify model environment variable
export TURTLEBOT3_MODEL=burger

# Test xacro expansion
rosrun xacro xacro $(rospack find turtlebot3_description)/urdf/turtlebot3_burger_for_autorace.urdf.xacro > /dev/null
```

## 3. Clean Process Termination
If nodes remain bound after exiting:
```bash
killall -9 gzserver gzclient rosmaster
pkill -f robo_treasure_hunt
```
