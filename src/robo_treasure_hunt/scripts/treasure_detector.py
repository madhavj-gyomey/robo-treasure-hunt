#!/usr/bin/env python3
"""
Robo Treasure Hunt - Treasure Detector
- Tracks robot position and orientation via /odom
- Reads treasure coordinates from config/treasures.yaml
- Calculates real-time distance and relative bearing arrow to nearest remaining treasure
- Publishes HUD treasure status to /game/treasures
- Detects collection, removes model from Gazebo via /gazebo/delete_model
- Emits visual marker effect to /visualization_marker
- Publishes /game/treasure_event for the game manager
"""

import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import String, Empty
from visualization_msgs.msg import Marker
from gazebo_msgs.srv import DeleteModel
import yaml
import math
import json


def get_bearing_arrow(angle_rad):
    """
    Returns directional arrow based on angle relative to robot forward heading.
    0 rad is forward, +pi/2 is left, -pi/2 is right, +/-pi is backward.
    """
    phi = math.atan2(math.sin(angle_rad), math.cos(angle_rad))
    pi = math.pi
    if abs(phi) < pi / 8:
        return "↑"
    elif pi / 8 <= phi < 3 * pi / 8:
        return "↖"
    elif 3 * pi / 8 <= phi < 5 * pi / 8:
        return "←"
    elif 5 * pi / 8 <= phi < 7 * pi / 8:
        return "↙"
    elif abs(phi) >= 7 * pi / 8:
        return "↓"
    elif -7 * pi / 8 < phi <= -5 * pi / 8:
        return "↘"
    elif -5 * pi / 8 < phi <= -3 * pi / 8:
        return "→"
    else:
        return "↗"


class TreasureDetector:
    def __init__(self):
        rospy.init_node("treasure_detector")

        config_path = rospy.get_param("~treasures_file", "")
        if not config_path:
            config_path = rospy.get_param("/treasure_hunt_controller/treasures_file", "")

        self.treasures = []
        self.detection_distance = 0.65

        if config_path:
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    self.treasures = config.get("treasures", [])
                    self.detection_distance = config.get("detection_distance", 0.65)
            except Exception as e:
                rospy.logerr("[TREASURE] Failed to load config %s: %s", config_path, e)

        if not self.treasures:
            self.treasures = [
                {"id": 1, "name": "Golden Idol", "model": "golden_idol", "x": 4.5, "y": 3.8, "z": 0.16},
                {"id": 2, "name": "Ancient Gem", "model": "ancient_gem", "x": -4.5, "y": 3.5, "z": 0.16},
                {"id": 3, "name": "Royal Crown", "model": "royal_crown", "x": 4.5, "y": -3.5, "z": 0.15}
            ]

        self.robot_x = -4.5
        self.robot_y = -3.5
        self.robot_yaw = 0.0
        self.found = set()
        self.reset_cooldown_until = 0.0

        # Publishers
        self.treasures_pub = rospy.Publisher("/game/treasures", String, queue_size=10)
        self.event_pub = rospy.Publisher("/game/treasure_event", String, queue_size=10)
        self.marker_pub = rospy.Publisher("/visualization_marker", Marker, queue_size=10)

        # Subscribers
        rospy.Subscriber("/odom", Odometry, self.odom_callback)
        rospy.Subscriber("/game/reset", Empty, self.reset_callback)

        # Periodic radar publish timer (10 Hz)
        self.timer = rospy.Timer(rospy.Duration(0.1), self.timer_callback)

        rospy.loginfo("[TREASURE] Detector active. Loaded %d treasures. Detection radius: %.2f m",
                      len(self.treasures), self.detection_distance)

    def odom_callback(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.robot_yaw = math.atan2(siny_cosp, cosy_cosp)

        # Skip proximity detection during reset cooldown
        if rospy.Time.now().to_sec() < self.reset_cooldown_until:
            return

        # Check proximity for collection
        for t in self.treasures:
            tid = t["id"]
            if tid in self.found:
                continue

            dx = self.robot_x - t["x"]
            dy = self.robot_y - t["y"]
            dist = math.sqrt(dx * dx + dy * dy)

            if dist <= self.detection_distance:
                self.collect_treasure(t)

    def collect_treasure(self, treasure):
        tid = treasure["id"]
        name = treasure["name"]
        model_name = treasure.get("model", "")

        self.found.add(tid)
        rospy.logwarn("💰 TREASURE STOLEN! %s (%d/%d)", name, len(self.found), len(self.treasures))

        # 1. Delete model from Gazebo
        if model_name:
            try:
                rospy.wait_for_service("/gazebo/delete_model", timeout=1.0)
                delete_srv = rospy.ServiceProxy("/gazebo/delete_model", DeleteModel)
                delete_srv(model_name)
                rospy.loginfo("[TREASURE] Deleted Gazebo model: %s", model_name)
            except Exception as e:
                rospy.logwarn("[TREASURE] Model deletion service call failed: %s", e)

        # 2. Publish visual effect marker
        self.publish_collection_marker(treasure)

        # 3. Publish event for Game Manager
        event_str = f"COLLECTED:{tid}:{name}:{model_name}"
        self.event_pub.publish(String(data=event_str))

    def publish_collection_marker(self, treasure):
        try:
            marker = Marker()
            marker.header.frame_id = "world"
            marker.header.stamp = rospy.Time.now()
            marker.ns = "treasure_sparks"
            marker.id = treasure["id"]
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD
            marker.pose.position.x = treasure["x"]
            marker.pose.position.y = treasure["y"]
            marker.pose.position.z = treasure.get("z", 0.16) + 0.15
            marker.scale.x = 0.5
            marker.scale.y = 0.5
            marker.scale.z = 0.5
            marker.color.a = 0.9
            marker.color.r = 1.0
            marker.color.g = 0.85
            marker.color.b = 0.1
            marker.lifetime = rospy.Duration(1.5)
            self.marker_pub.publish(marker)
        except Exception:
            pass

    def timer_callback(self, event):
        nearest_treasure = None
        nearest_dist = float("inf")
        nearest_bearing = 0.0
        nearest_arrow = "↑"

        for t in self.treasures:
            if t["id"] in self.found:
                continue

            dx = t["x"] - self.robot_x
            dy = t["y"] - self.robot_y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_treasure = t

                world_angle = math.atan2(dy, dx)
                rel_angle = world_angle - self.robot_yaw
                nearest_bearing = math.atan2(math.sin(rel_angle), math.cos(rel_angle))
                nearest_arrow = get_bearing_arrow(nearest_bearing)

        all_collected = (len(self.found) >= len(self.treasures))

        status_data = {
            "total": len(self.treasures),
            "collected": len(self.found),
            "remaining": len(self.treasures) - len(self.found),
            "all_collected": all_collected,
            "nearest_name": nearest_treasure["name"] if nearest_treasure else "None",
            "nearest_dist": round(nearest_dist, 1) if nearest_treasure else 0.0,
            "nearest_bearing": round(nearest_bearing, 2) if nearest_treasure else 0.0,
            "nearest_arrow": nearest_arrow if not all_collected else "★",
            "treasures": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "collected": (t["id"] in self.found)
                }
                for t in self.treasures
            ]
        }

        self.treasures_pub.publish(String(data=json.dumps(status_data)))

    def reset_callback(self, msg):
        rospy.loginfo("[TREASURE] Detector reset received. Setting cooldown.")
        self.found.clear()
        self.reset_cooldown_until = rospy.Time.now().to_sec() + 1.2


def main():
    try:
        TreasureDetector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
