<div align="center">

![Robo Treasure Hunt](Assets/banner_robo_treasure_hunt.svg)

# 00.0 // ROBO TREASURE HUNT

```
SYS_ID: RTH-TB3-01  ·  REF: GAZEBO-11-ODE  ·  FRAMEWORK: ROS 1 NOETIC  ·  STATUS: OPERATIONAL
COORDINATES: [-4.50, -3.50, 0.08]  ·  PAYLOAD: 300 PTS  ·  SURVEILLANCE: 3 TIMED ZONES
```

**Autonomous Infiltration, Artifact Retrieval &amp; Timed Security Evasion Simulation**  
*Built with ROS 1 Noetic, Gazebo 11, TurtleBot3 Burger &amp; PyQt5*

---

</div>

## 01.0 // SYSTEM SPECIFICATION & ARCHITECTURAL PREMISE

Robo Treasure Hunt is an event-driven robotics simulation engineered on **ROS 1 Noetic** and **Gazebo 11**. The system places a differential-drive **TurtleBot3 Burger** within a multi-corridor indoor museum labyrinth (`worlds/museum.world`). The robot's operational mandate is to locate, approach, and recover three high-value historical artifacts while evading three continuous, timed radial surveillance detection sectors.

The computational pipeline couples a **PyQt5 Operator Surveillance Station** streaming 30 FPS first-person video from the robot's onboard sensor suite (`/camera/image_raw`), an active Euclidean bearing radar, dynamic Gazebo scene graph manipulation via ROS services, and a discrete-step velocity controller with high-speed boost gearing.

| SPECIFICATION ID | ARCHITECTURAL PARAMETER | SUBSYSTEM IMPLEMENTATION |
| :--- | :--- | :--- |
| `PLATFORM.01` | **Mobile Base** | TurtleBot3 Burger (Differential Drive, 160mm Wheelbase) |
| `SENSING.01` | **Perception Suite** | LDS-01 360° 2D LiDAR (1.8 kHz) + FPV Camera (30 FPS) |
| `PHYSICS.01` | **Simulation Core** | Gazebo 11.14 (ODE Solvers, 1 kHz Physics Step, `museum.world`) |
| `MIDDLEWARE.01`| **ROS Distribution** | ROS 1 Noetic Ninjemys on Ubuntu 20.04 LTS |
| `INTERFACE.01` | **Operator Station** | PyQt5 Zero-Dependency Surveillance Station |
| `MISSION.01`   | **Target Artifacts** | Golden Idol, Ancient Gem, Royal Crown (100 Pts Each = 300 Pts Total) |
| `SECURITY.01`  | **Surveillance Grid**| 3 Radial Zones (North, Central, Lower) with Two-Tier Dwell Clocks |
| `MOTION.01`    | **Kinematics** | Discrete Inertia-Braked Translation & 2.0x Boost Gearing |

---

## 02.0 // SPATIAL LABYRINTH & ARTIFACT RECOVERY

The operational theater is a closed architectural labyrinth featuring asymmetric boundary partitions, blind corridors, and elevated pedestals housing individual physical artifact entities.

<div align="center">

![Gazebo Museum World Overhead View](Screenshots/gazebo_museum_world_overhead.png)
*FIG 01. Orthographic architectural projection of `worlds/museum.world` showing internal wall corridors, three glowing cylindrical security sectors (cyan), artifact pedestal locations, and the robot spawn anchor.*

</div>

<br>

<div align="center">

![TurtleBot3 Burger in Museum Corridor](Screenshots/gazebo_turtlebot3_museum_corridor.png)
*FIG 02. TurtleBot3 Burger deployed within museum corridor facing the Lower Gallery security threshold.*

</div>

### 02.1 // Artifact Telemetry Matrix
Artifacts are defined in `config/treasures.yaml` and spawned dynamically on pedestals:

| REF | ARTIFACT ENTITY | CARTESIAN COORDINATE $(X, Y, Z)$ | PROXIMITY RADIUS | PHYSICAL GEOMETRY |
| :--- | :--- | :--- | :--- | :--- |
| `ART.01` | **Golden Idol** | `(+4.50, +3.80, +0.16)` | $0.65\text{ m}$ (Euclidean) | Gold Pedestal + Cylindrical Idol Link |
| `ART.02` | **Ancient Gem** | `(-4.50, +3.50, +0.16)` | $0.65\text{ m}$ (Euclidean) | Slate Plinth + Cyan Sphere Link |
| `ART.03` | **Royal Crown** | `(+4.50, -3.50, +0.15)` | $0.65\text{ m}$ (Euclidean) | Marble Stand + Ruby Ring Link |

### 02.2 // Physical Deletion on Acquisition
1. `/treasure_detector` tracks the Euclidean distance between the robot base frame (`/odom`) and each active artifact position.
2. When distance $d \le 0.65\text{ m}$, a capture event is confirmed.
3. The node invokes the Gazebo master service `/gazebo/delete_model`, physically erasing the artifact entity from the simulation world graph.
4. `/game_manager` awards **+100 points**, registers the acquired entity, and broadcasts updated state telemetry to `/game/state` and `/game/score`.

<div align="center">

![Mission Complete Modal](Screenshots/hud_mission_complete.png)
*FIG 03. Operator HUD upon successful acquisition of all three museum artifacts (300 points secured).*

</div>

---

## 03.0 // COMPUTATIONAL GRAPH & ROS TOPOLOGY

The system executes as six decoupled ROS nodes coordinating over asynchronous publish-subscribe buses and synchronous Gazebo RPC services.

<div align="center">

![ROS Architecture Diagram](Assets/architecture_robo_treasure_hunt.svg)
*FIG 04. ROS computational graph detailing node boundaries, topic message types, Gazebo service interfaces, and data flow across simulation, processing, and operator layers.*

</div>

### 03.1 // Node Communication Directory

| NODE IDENTIFIER | SOURCE SCRIPT | SUBSCRIBED TOPICS | PUBLISHED TOPICS | SERVICE INTERFACES |
| :--- | :--- | :--- | :--- | :--- |
| `/game_manager` | `scripts/game_manager.py` | `/game/treasure_event`<br>`/game/security`<br>`/game/reset` | `/game/state`<br>`/game/score` | `/gazebo/set_model_state`<br>`/gazebo/spawn_sdf_model`<br>`/gazebo/delete_model` |
| `/treasure_detector` | `scripts/treasure_detector.py` | `/odom`<br>`/game/reset` | `/game/treasures`<br>`/game/treasure_event`<br>`/visualization_marker` | `/gazebo/delete_model` |
| `/security_detector` | `scripts/security_detector.py` | `/odom`<br>`/game/reset` | `/game/security` | *None* |
| `/game_hud` | `scripts/game_hud.py` | `/camera/image_raw`<br>`/game/state`<br>`/game/treasures`<br>`/game/security`<br>`/game/score` | `/game/reset`<br>`/cmd_vel` | *None* |
| `/player_controller` | `scripts/player_controller.py` | Standard Input (POSIX raw) | `/cmd_vel`<br>`/game/speed_mode`<br>`/game/reset` | *None* |
| `/gazebo` | `launch/treasure_hunt.launch` | `/cmd_vel` | `/odom`<br>`/camera/image_raw`<br>`/scan` | Physics Engine Core |

---

## 04.0 // SURVEILLANCE CADENCE & RADIAL DETECTION ZONES

Facility surveillance is governed by three continuous cylindrical security sectors defined in `config/security.yaml`.

<div align="center">

![Security Zone Logic Diagram](Assets/security_zone_logic.svg)
*FIG 05. Two-tier dwell timer state machine showing threshold transitions between CLEAR, SUSPICIOUS, and ALARM.*

</div>

### 04.1 // Security Sector Specifications

| SECTOR ID | GALLERY ZONE | CENTER $(X, Y)$ | DETECTION RADIUS | SUSPICION THRESHOLD | ALARM THRESHOLD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SEC.01` | **North Gallery** | `(-1.50, +2.00)` | $1.0\text{ m}$ | $3.0\text{ s}$ dwell limit | $6.0\text{ s}$ lockout trigger |
| `SEC.02` | **Central Gallery** | `(+1.00, +0.00)` | $0.8\text{ m}$ | $2.0\text{ s}$ dwell limit | $5.0\text{ s}$ lockout trigger |
| `SEC.03` | **Lower Gallery** | `(+0.00, -3.50)` | $1.0\text{ m}$ | $4.0\text{ s}$ dwell limit | $8.0\text{ s}$ lockout trigger |

### 04.2 // Intrusion Dynamics
For robot coordinates $(x_r, y_r)$ and zone center $(x_z, y_z)$ with radius $R$:

$$d_z = \sqrt{(x_r - x_z)^2 + (y_r - y_z)^2}$$

- **State 1: CLEAR** — $d_z > R$. Surveillance is dormant; stealth integrity intact.
- **State 2: SUSPICIOUS** — $d_z \le R$ and dwell duration $t_{\text{dwell}} \ge t_{\text{suspicion}}$. The Operator HUD triggers an active alert banner with a real-time countdown to alarm.
- **State 3: ALARM** — $t_{\text{dwell}} \ge t_{\text{alarm}}$. Mission failure triggers. `/game_manager` shifts to `GAME_FAILED`, disabling wheel drives.

<div align="center">

![Game Failed Alarm Modal](Screenshots/hud_game_failed_alarm.png)
*FIG 06. Intrusion alarm trigger: failure to evade the security sector before the dwell threshold terminates the mission.*

</div>

---

## 05.0 // OPERATOR HUD & SENSOR TELEMETRY

The primary operator interface (`scripts/game_hud.py`) is an autonomous **PyQt5** application delivering real-time sensory feedback without third-party web or OpenCV dependencies.

<div align="center">

![Operator HUD Active Gameplay](Screenshots/hud_gameplay_fpv_radar_suspicious.png)
*FIG 07. Live operator interface displaying real-time FPV camera stream (`/camera/image_raw`), directional radar pointing to Royal Crown (Distance: 4.8 m, Arrow: ↖), and active security countdown alert (Lower Gallery, 2.8s remaining).*

</div>

### 05.1 // Radar Vector Quantisation
Target bearing is computed relative to the robot heading $\theta_r$ and artifact coordinate $(x_t, y_t)$:

$$\Delta x = x_t - x_r, \quad \Delta y = y_t - y_r$$
$$\theta_{\text{target}} = \operatorname{atan2}(\Delta y, \Delta x)$$
$$\phi = \operatorname{atan2}(\sin(\theta_{\text{target}} - \theta_r), \cos(\theta_{\text{target}} - \theta_r))$$

The continuous angle $\phi \in [-\pi, \pi]$ is quantised into an 8-compass directional arrow:

| RELATIVE BEARING $\phi$ | COMPASS ARROW | SPATIAL ORIENTATION |
| :--- | :--- | :--- |
| $|\phi| < \pi/8$ | `↑` | Direct Ahead |
| $\pi/8 \le \phi < 3\pi/8$ | `↖` | Forward Left |
| $3\pi/8 \le \phi < 5\pi/8$ | `←` | Direct Left |
| $5\pi/8 \le \phi < 7\pi/8$ | `↙` | Rear Left |
| $|\phi| \ge 7\pi/8$ | `↓` | Direct Behind |
| $-7\pi/8 < \phi \le -5\pi/8$ | `↘` | Rear Right |
| $-5\pi/8 < \phi \le -3\pi/8$ | `→` | Direct Right |
| $-3\pi/8 < \phi \le -\pi/8$ | `↗` | Forward Right |

---

## 06.0 // DISCRETE INERTIA-BRAKED KINEMATICS

Locomotion is governed by `scripts/player_controller.py`, which executes non-blocking keyboard tracking in raw POSIX terminal mode.

```
======================================================================
                     ROBO TREASURE HUNT — CONTROLLER                  
======================================================================
  KEYBOARD INPUTS
    <kbd>W</kbd> / <kbd>S</kbd>         : Move Forward / Backward (discrete step, 0.30s)
    <kbd>A</kbd> / <kbd>D</kbd>         : Turn Left / Right (discrete rotation, 0.20s)
    <kbd>SHIFT</kbd> + KEY : 2.0x Speed Boost Mode (uppercase input)
    <kbd>R</kbd>                 : Reset / Replay Mission
    <kbd>Q</kbd>                 : Terminate Controller
----------------------------------------------------------------------
  VELOCITY SPECIFICATIONS
    Normal Speed : Linear 0.50 m/s  |  Angular 1.40 rad/s
    Boost Speed  : Linear 0.90 m/s  |  Angular 2.00 rad/s
======================================================================
```

### 06.1 // Inertia Braking Principle
To eliminate slip and inertia drift common in simulated differential-drive robots:
1. Key press publishes velocity on `/cmd_vel` (`geometry_msgs/Twist`).
2. Velocity is held for a discrete interval ($0.30\text{s}$ for translation, $0.20\text{s}$ for turns).
3. The controller immediately transmits a zeroed `Twist()` message (`linear.x = 0.0, angular.z = 0.0`), enforcing active stopping.

---

## 07.0 // CONFIGURATION REGISTRIES

Operational thresholds are stored in version-controlled YAML files:

### 07.1 // Game Parameters (`config/game.yaml`)
```yaml
player:
  normal_linear_speed: 0.50
  boost_linear_speed: 0.90
  normal_angular_speed: 1.40
  boost_angular_speed: 2.00
  move_time: 0.30
  turn_time: 0.20

rules:
  score_per_treasure: 100
  total_treasures: 3

spawn:
  x: -4.5
  y: -3.5
  z: 0.08
  yaw: 0.0
```

---

## 08.0 // DEPLOYMENT & ENVIRONMENT SETUP

### 08.1 // Prerequisites
- **OS**: Ubuntu 20.04 LTS (Native or WSL2)
- **ROS Version**: ROS 1 Noetic Ninjemys (`/opt/ros/noetic`)
- **Physics Core**: Gazebo 11
- **Python**: Python 3.8+ with `PyQt5`, `numpy`, and `PyYAML`
- **Display**: Active X11 server (WSLg on Windows 11 sets `DISPLAY=:0` automatically)

### 08.2 // Package Dependencies
```bash
sudo apt-get update
sudo apt-get install -y \
  ros-noetic-desktop-full \
  ros-noetic-turtlebot3-description \
  ros-noetic-turtlebot3-gazebo \
  ros-noetic-turtlebot3-teleop \
  python3-pyqt5 \
  python3-yaml \
  python3-numpy \
  xterm
```

### 08.3 // Catkin Build
```bash
source /opt/ros/noetic/setup.bash
cd ~/robo_treasure_hunt_ws
catkin_make
source devel/setup.bash
```

### 08.4 // Launching Simulation
```bash
export DISPLAY=:0
export TURTLEBOT3_MODEL=burger
roslaunch robo_treasure_hunt treasure_hunt.launch
```

---

## 09.0 // EMPIRICAL VERIFICATION & LOG TELEMETRY

<div align="center">

![ROS Execution Terminal Log](Screenshots/ros_execution_terminal_log.png)
*FIG 08. Live execution terminal telemetry recording node initializations, Gazebo model deletions, security zone crossings, and mission reset cycles.*

</div>

Empirical performance metrics measured during simulation runs:
- **Model Deletion Latency**: $< 45\text{ ms}$ via `/gazebo/delete_model`.
- **Odometry Sampling Rate**: $10\text{ Hz}$ continuous position and bearing recalculation.
- **FPV Video Stream**: $30\text{ FPS}$ sustained throughput at native resolution.
- **Full Mission Reset Latency**: $< 500\text{ ms}$ to clear scene entities, respawn SDF artifacts, and reset robot transform.

---

## 10.0 // REPOSITORY TAXONOMY

```text
robo_treasure_hunt_ws/
├── .catkin_workspace
├── .gitignore
├── README.md
│
├── Assets/
│   ├── banner_robo_treasure_hunt.svg
│   ├── architecture_robo_treasure_hunt.svg
│   └── security_zone_logic.svg
│
├── Documentation/
│   ├── architecture.md
│   ├── stealth_mechanics.md
│   └── troubleshooting.md
│
├── Screenshots/
│   ├── gazebo_museum_world_overhead.png
│   ├── gazebo_turtlebot3_museum_corridor.png
│   ├── hud_gameplay_fpv_radar_suspicious.png
│   ├── hud_gameplay_fpv_radar_clear.png
│   ├── hud_loading_mission_ready.png
│   ├── hud_mission_complete.png
│   ├── hud_game_failed_alarm.png
│   ├── player_controller_terminal.png
│   ├── ros_execution_terminal_log.png
│   └── project_directory_tree_ide.png
│
└── src/
    ├── CMakeLists.txt
    └── robo_treasure_hunt/
        ├── CMakeLists.txt
        ├── package.xml
        │
        ├── config/
        │   ├── game.yaml
        │   ├── security.yaml
        │   └── treasures.yaml
        │
        ├── launch/
        │   └── treasure_hunt.launch
        │
        ├── scripts/
        │   ├── game_hud.py
        │   ├── game_manager.py
        │   ├── player_controller.py
        │   ├── security_detector.py
        │   └── treasure_detector.py
        │
        └── worlds/
            └── museum.world
```

---

## 11.0 // TECHNICAL DOCUMENTATION INDEX

- [System Architecture & Node Topology](Documentation/architecture.md)
- [Stealth & Detection Mathematics](Documentation/stealth_mechanics.md)
- [Troubleshooting & Setup Guide](Documentation/troubleshooting.md)

---

## 12.0 // AUTHOR & LICENSE

- **Author**: Madhav J ([@madhavj-gyomey](https://github.com/madhavj-gyomey))
- **Repository**: [madhavj-gyomey/robo-treasure-hunt](https://github.com/madhavj-gyomey/robo-treasure-hunt)
- **License**: MIT Open Source License
