#!/usr/bin/env python3
"""
Robo Treasure Hunt - Game Manager
Central game state authority responsible for:
- Score tracking
- Mission state machine: LOADING, PLAYING, SUSPICIOUS, ALARM, GAME_FAILED, MISSION_COMPLETE, RESETTING
- Robot spawn reset & Gazebo model re-spawning on reset
- Event coordination
"""

import rospy
from std_msgs.msg import String, Int32, Empty
from geometry_msgs.msg import Twist, Pose, Point, Quaternion
from gazebo_msgs.msg import ModelState
from gazebo_msgs.srv import SetModelState, SpawnModel, DeleteModel
import yaml
import json
import time

TREASURE_SDF_TEMPLATES = {
    "golden_idol": """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="golden_idol">
    <static>true</static>
    <link name="link">
      <collision name="collision">
        <geometry><cylinder><radius>0.12</radius><length>0.32</length></cylinder></geometry>
      </collision>
      <visual name="pedestal">
        <pose>0 0 -0.10 0 0 0</pose>
        <geometry><box><size>0.24 0.24 0.08</size></box></geometry>
        <material><ambient>0.8 0.5 0.05 1</ambient><diffuse>0.95 0.70 0.10 1</diffuse><specular>1 1 1 1</specular><emissive>0.20 0.12 0.02 1</emissive></material>
      </visual>
      <visual name="idol_body">
        <pose>0 0 0.04 0 0 0</pose>
        <geometry><cylinder><radius>0.10</radius><length>0.20</length></cylinder></geometry>
        <material><ambient>0.85 0.55 0.05 1</ambient><diffuse>0.98 0.75 0.12 1</diffuse><specular>1 1 1 1</specular><emissive>0.25 0.15 0.02 1</emissive></material>
      </visual>
    </link>
  </model>
</sdf>""",
    "ancient_gem": """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="ancient_gem">
    <static>true</static>
    <link name="link">
      <collision name="collision">
        <geometry><sphere><radius>0.12</radius></sphere></geometry>
      </collision>
      <visual name="pedestal">
        <pose>0 0 -0.10 0 0 0</pose>
        <geometry><cylinder><radius>0.12</radius><length>0.08</length></cylinder></geometry>
        <material><ambient>0.2 0.2 0.25 1</ambient><diffuse>0.3 0.3 0.35 1</diffuse></material>
      </visual>
      <visual name="gem_sphere">
        <pose>0 0 0.04 0 0 0</pose>
        <geometry><sphere><radius>0.12</radius></sphere></geometry>
        <material><ambient>0.05 0.6 0.85 1</ambient><diffuse>0.10 0.80 0.95 1</diffuse><specular>1 1 1 1</specular><emissive>0.10 0.40 0.55 1</emissive></material>
      </visual>
    </link>
  </model>
</sdf>""",
    "royal_crown": """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="royal_crown">
    <static>true</static>
    <link name="link">
      <collision name="collision">
        <geometry><box><size>0.26 0.26 0.26</size></box></geometry>
      </collision>
      <visual name="cushion">
        <pose>0 0 -0.06 0 0 0</pose>
        <geometry><box><size>0.26 0.26 0.10</size></box></geometry>
        <material><ambient>0.6 0.05 0.6 1</ambient><diffuse>0.75 0.10 0.75 1</diffuse><specular>0.8 0.8 0.8 1</specular><emissive>0.15 0.02 0.15 1</emissive></material>
      </visual>
      <visual name="crown_ring">
        <pose>0 0 0.04 0 0 0</pose>
        <geometry><cylinder><radius>0.11</radius><length>0.12</length></cylinder></geometry>
        <material><ambient>0.85 0.55 0.05 1</ambient><diffuse>0.95 0.70 0.10 1</diffuse><specular>1 1 1 1</specular><emissive>0.20 0.12 0.02 1</emissive></material>
      </visual>
    </link>
  </model>
</sdf>"""
}


class GameManager:
    def __init__(self):
        rospy.init_node("game_manager")

        # Load configs
        treasures_file = rospy.get_param("~treasures_file", "")
        game_file = rospy.get_param("~game_file", "")

        self.treasures_config = []
        if treasures_file:
            try:
                with open(treasures_file, "r") as f:
                    self.treasures_config = yaml.safe_load(f).get("treasures", [])
            except Exception as e:
                rospy.logerr("[GAME] Could not load treasures file: %s", e)

        self.total_treasures = len(self.treasures_config) if self.treasures_config else 3
        self.points_per_treasure = 100
        self.spawn_pos = (-4.5, -3.5, 0.08)

        if game_file:
            try:
                with open(game_file, "r") as f:
                    gcfg = yaml.safe_load(f)
                    self.points_per_treasure = gcfg.get("rules", {}).get("score_per_treasure", 100)
                    sp = gcfg.get("spawn", {})
                    self.spawn_pos = (sp.get("x", -4.5), sp.get("y", -3.5), sp.get("z", 0.08))
            except Exception as e:
                rospy.logwarn("[GAME] Could not load game config: %s", e)

        # Game state variables
        self.state = "PLAYING"
        self.score = 0
        self.collected_ids = set()
        self.deleted_models = set()
        self.resetting = False

        # Publishers
        self.state_pub = rospy.Publisher("/game/state", String, queue_size=10, latch=True)
        self.score_pub = rospy.Publisher("/game/score", Int32, queue_size=10, latch=True)
        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)

        # Subscribers
        rospy.Subscriber("/game/treasure_event", String, self.treasure_event_callback)
        rospy.Subscriber("/game/security", String, self.security_callback)
        rospy.Subscriber("/game/reset", Empty, self.reset_callback)

        # Initial announcements
        self.publish_state()
        self.publish_score()

        rospy.loginfo("[GAME] Mission started. Score: 0, Total Treasures: %d", self.total_treasures)

        # Periodic state publication timer (5 Hz)
        self.timer = rospy.Timer(rospy.Duration(0.2), self.timer_callback)

    def publish_state(self):
        self.state_pub.publish(String(data=self.state))

    def publish_score(self):
        self.score_pub.publish(Int32(data=self.score))

    def timer_callback(self, event):
        self.publish_state()
        self.publish_score()

    def treasure_event_callback(self, msg):
        if self.resetting or self.state in ["GAME_FAILED", "MISSION_COMPLETE", "RESETTING"]:
            return

        try:
            parts = msg.data.split(":")
            if parts[0] == "COLLECTED" and len(parts) >= 3:
                tid = int(parts[1])
                name = parts[2]
                model_name = parts[3] if len(parts) > 3 else ""

                if tid not in self.collected_ids:
                    self.collected_ids.add(tid)
                    if model_name:
                        self.deleted_models.add(model_name)
                    self.score += self.points_per_treasure

                    rospy.loginfo("[GAME] Treasure collected: %s (+%d pts). Score: %d (%d/%d)",
                                  name, self.points_per_treasure, self.score,
                                  len(self.collected_ids), self.total_treasures)

                    self.publish_score()

                    if len(self.collected_ids) >= self.total_treasures:
                        self.state = "MISSION_COMPLETE"
                        rospy.logwarn("[GAME] Mission complete! All treasures collected. Final score: %d", self.score)
                        self.cmd_pub.publish(Twist())
                        self.publish_state()
        except Exception as e:
            rospy.logerr("[GAME] Error parsing treasure event: %s", e)

    def security_callback(self, msg):
        if self.resetting or self.state in ["GAME_FAILED", "MISSION_COMPLETE", "RESETTING"]:
            return

        try:
            data = {}
            if msg.data.startswith("{"):
                data = json.loads(msg.data)
            else:
                for item in msg.data.split(","):
                    if ":" in item:
                        k, v = item.split(":", 1)
                        data[k.strip()] = v.strip()

            sec_status = data.get("status", "CLEAR")

            if sec_status == "ALARM":
                self.state = "GAME_FAILED"
                rospy.logerr("[GAME] GAME FAILED! Security alarm triggered in zone: %s", data.get("zone", "Security"))
                self.cmd_pub.publish(Twist())
                self.publish_state()
            elif sec_status == "SUSPICIOUS" and self.state == "PLAYING":
                self.state = "SUSPICIOUS"
                self.publish_state()
            elif sec_status == "CLEAR" and self.state == "SUSPICIOUS":
                self.state = "PLAYING"
                self.publish_state()
        except Exception as e:
            rospy.logerr("[GAME] Error processing security msg: %s", e)

    def reset_callback(self, msg):
        rospy.loginfo("[GAME] Reset requested. Resetting simulation...")
        self.resetting = True
        self.state = "RESETTING"
        self.publish_state()

        # Stop robot
        self.cmd_pub.publish(Twist())

        # 1. Reset robot pose in Gazebo FIRST
        try:
            rospy.wait_for_service("/gazebo/set_model_state", timeout=3.0)
            set_state = rospy.ServiceProxy("/gazebo/set_model_state", SetModelState)
            state_msg = ModelState()
            state_msg.model_name = rospy.get_param("~robot_model_name", "turtlebot3_burger")
            state_msg.pose.position.x = self.spawn_pos[0]
            state_msg.pose.position.y = self.spawn_pos[1]
            state_msg.pose.position.z = self.spawn_pos[2]
            state_msg.pose.orientation.x = 0.0
            state_msg.pose.orientation.y = 0.0
            state_msg.pose.orientation.z = 0.0
            state_msg.pose.orientation.w = 1.0
            state_msg.twist = Twist()
            state_msg.reference_frame = "world"
            set_state(state_msg)
            rospy.loginfo("[GAME] Robot pose reset to (%0.2f, %0.2f, %0.2f)",
                          self.spawn_pos[0], self.spawn_pos[1], self.spawn_pos[2])
        except Exception as e:
            rospy.logwarn("[GAME] Could not reset robot pose via Gazebo: %s", e)

        rospy.sleep(0.3)

        # 2. Respawn deleted treasures in Gazebo
        try:
            rospy.wait_for_service("/gazebo/spawn_sdf_model", timeout=2.0)
            spawn_srv = rospy.ServiceProxy("/gazebo/spawn_sdf_model", SpawnModel)

            for t in self.treasures_config:
                mname = t.get("model", "")
                if mname in self.deleted_models and mname in TREASURE_SDF_TEMPLATES:
                    p = Pose()
                    p.position = Point(x=t.get("x", 0.0), y=t.get("y", 0.0), z=t.get("z", 0.16))
                    p.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
                    spawn_srv(mname, TREASURE_SDF_TEMPLATES[mname], "", p, "world")
                    rospy.loginfo("[GAME] Respawned model: %s at (%0.2f, %0.2f)", mname, t["x"], t["y"])
        except Exception as e:
            rospy.logwarn("[GAME] Treasure respawn check: %s", e)

        self.deleted_models.clear()
        self.collected_ids.clear()
        self.score = 0

        rospy.sleep(0.2)
        self.resetting = False
        self.state = "PLAYING"
        self.publish_score()
        self.publish_state()
        rospy.loginfo("[GAME] Mission reset complete. Game state: PLAYING")


def main():
    try:
        GameManager()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
