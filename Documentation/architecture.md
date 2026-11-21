# Robo Treasure Hunt — System Architecture & Node Topology

## 1. Overview
Robo Treasure Hunt is an event-driven stealth simulation constructed on ROS 1 Noetic and Gazebo 11. The system simulates a TurtleBot3 Burger operating inside a complex indoor museum labyrinth, locating and acquiring hidden artifacts while evading timed radial security detection zones.

```
+-----------------------------------------------------------------------------------+
|                                 ROS MASTER CORE                                   |
+-----------------------------------------------------------------------------------+
       ^                        ^                        ^                   ^
       | /odom                  | /cmd_vel               | /camera/image_raw | Gazebo Srv
       v                        v                        v                   v
[gazebo_ros]             [player_controller]      [game_hud (PyQt5)]   [game_manager]
  • museum.world           • POSIX raw input        • FPV Camera 30 FPS  • Mission State
  • LDS-01 LiDAR           • Discrete steps         • Target Radar       • Model Spawner
  • FPV Pi Camera          • 2.0x Boost             • Security Bar       • Reset Arbiter
       |                        |                        ^                   ^
       +---> [treasure_detector]+------------------------+                   |
       |       • Distance & Bearing Arrow                                    |
       +---> [security_detector]---------------------------------------------+
               • Timed radial zones (3s/6s, 2s/5s, 4s/8s)
```

## 2. Node Specifications

### 2.1 `/game_manager` (`scripts/game_manager.py`)
- **Authority**: Master state machine and match arbitrator.
- **Subscribed Topics**:
  - `/game/treasure_event` (`std_msgs/String`): Artifact collection events.
  - `/game/security` (`std_msgs/String`): Radial zone intrusion status and timer updates.
  - `/game/reset` (`std_msgs/Empty`): Hardware or HUD reset commands.
  - `/gazebo/model_states` (`gazebo_msgs/ModelStates`): Real-time pose verification.
- **Published Topics**:
  - `/game/state` (`std_msgs/String`): JSON telemetry payload containing match state, points, elapsed duration, and targets.
  - `/game/score` (`std_msgs/Int32`): Current cumulative match score.
- **Service Clients**:
  - `/gazebo/set_model_state`: Repositions the robot to `(-4.50, -3.50, 0.08, yaw=0.0)`.
  - `/gazebo/spawn_sdf_model`: Dynamically injects the 3 artifact SDF models into Gazebo on reset.
  - `/gazebo/delete_model`: Erases collected artifacts from the 3D physics environment.

### 2.2 `/treasure_detector` (`scripts/treasure_detector.py`)
- **Subscribed Topics**:
  - `/odom` (`nav_msgs/Odometry`): High-frequency odometry feedback from TurtleBot3 wheel encoders.
  - `/game/reset` (`std_msgs/Empty`): Resets local acquired artifact cache.
- **Published Topics**:
  - `/game/treasures` (`std_msgs/String`): Real-time JSON telemetry detailing nearest target, Euclidean distance, angular bearing, and direction symbol.
  - `/game/treasure_event` (`std_msgs/String`): Emitted when Euclidean distance $d \le 0.65\text{ m}$.
  - `/visualization_marker` (`visualization_msgs/Marker`): Visual RViz marker cues.

### 2.3 `/security_detector` (`scripts/security_detector.py`)
- **Configuration**: `config/security.yaml`.
- **Subscribed Topics**:
  - `/odom` (`nav_msgs/Odometry`): Odometric spatial position $(x, y)$.
  - `/game/reset` (`std_msgs/Empty`): Clears active zone timers and alarm registries.
- **Published Topics**:
  - `/game/security` (`std_msgs/String`): JSON zone telemetry including active zone ID, elapsed dwell time, threshold limits, and remaining alarm window.

### 2.4 `/game_hud` (`scripts/game_hud.py`)
- **Framework**: PyQt5 graphical application with QTimer-driven ROS spin cycle.
- **Image Pipeline**: Subscribes to `/camera/image_raw` (`sensor_msgs/Image`), unpacking RGB8/BGR8 byte buffers into `QImage` formats for 30 FPS FPV video streaming without OpenCV overhead.

### 2.5 `/player_controller` (`scripts/player_controller.py`)
- **Terminal Execution**: Runs inside dedicated terminal window (`xterm -e`).
- **Input Loop**: POSIX `termios` and `tty.setraw` reading non-blocking standard input via `select.select`.
- **Discrete Step Kinematics**: Publishes velocity burst on `/cmd_vel` for fixed duration (`0.30s` for linear translation, `0.20s` for rotation), followed immediately by explicit `Twist()` with zero values to eliminate inertia drift.
