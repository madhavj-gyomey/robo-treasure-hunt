#!/usr/bin/env python3
"""
Robo Treasure Hunt - Security Detector
- Subscribes to /odom
- Loads security zones from config/security.yaml
- Detects entry into security zones
- Tracks suspicion and alarm timers
- Publishes real-time security status to /game/security
- Clears alarm state when robot leaves or on /game/reset
"""

import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import String, Empty
import yaml
import math
import json


class SecurityDetector:
    def __init__(self):
        rospy.init_node("security_detector")

        config_path = rospy.get_param("~security_file", "")
        self.zones = []

        if config_path:
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    self.zones = config.get("security_zones", [])
            except Exception as e:
                rospy.logerr("[SECURITY] Failed to load config %s: %s", config_path, e)

        if not self.zones:
            rospy.logwarn("[SECURITY] No security zones loaded from config, using default coordinates")
            self.zones = [
                {"id": 1, "name": "North Gallery Security", "x": -1.5, "y": 2.0, "detection_radius": 1.0, "suspicion_time": 3.0, "alarm_time": 6.0},
                {"id": 2, "name": "Central Gallery Security", "x": 1.0, "y": 0.0, "detection_radius": 0.8, "suspicion_time": 2.0, "alarm_time": 5.0},
                {"id": 3, "name": "Lower Gallery Security", "x": 0.0, "y": -3.5, "detection_radius": 1.0, "suspicion_time": 4.0, "alarm_time": 8.0}
            ]

        self.robot_x = 0.0
        self.robot_y = 0.0

        # Zone tracking: zone_id -> entry_timestamp
        self.zone_entry_time = {}
        self.alarmed_zones = set()

        # Publishers & Subscribers
        self.security_pub = rospy.Publisher("/game/security", String, queue_size=10)
        rospy.Subscriber("/odom", Odometry, self.odom_callback)
        rospy.Subscriber("/game/reset", Empty, self.reset_callback)

        # Periodic timer (10 Hz)
        self.timer = rospy.Timer(rospy.Duration(0.1), self.timer_callback)

        rospy.loginfo("[SECURITY] System active with %d security zones.", len(self.zones))

    def odom_callback(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

    def timer_callback(self, event):
        current_time = rospy.Time.now().to_sec()

        active_zone = None
        current_status = "CLEAR"
        zone_name = "None"
        elapsed_sec = 0.0
        remaining_alarm = 0.0
        suspicion_t = 3.0
        alarm_t = 6.0

        for zone in self.zones:
            zid = zone["id"]
            dx = self.robot_x - zone["x"]
            dy = self.robot_y - zone["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            radius = zone["detection_radius"]

            if dist <= radius:
                active_zone = zone
                zone_name = zone["name"]
                suspicion_t = zone["suspicion_time"]
                alarm_t = zone["alarm_time"]

                if zid not in self.zone_entry_time:
                    self.zone_entry_time[zid] = current_time
                    rospy.logwarn("⚠️ SECURITY ZONE ENTERED: %s", zone_name)

                elapsed_sec = current_time - self.zone_entry_time[zid]
                remaining_alarm = max(0.0, alarm_t - elapsed_sec)

                if elapsed_sec >= alarm_t:
                    current_status = "ALARM"
                    if zid not in self.alarmed_zones:
                        self.alarmed_zones.add(zid)
                        rospy.logerr("🚨🚨 SECURITY ALARM IN %s! Intruder detected for %.1fs! 🚨🚨",
                                     zone_name, elapsed_sec)
                elif elapsed_sec >= suspicion_t:
                    current_status = "SUSPICIOUS"
                else:
                    current_status = "CLEAR"

                break  # Process the first active zone
            else:
                if zid in self.zone_entry_time:
                    rospy.loginfo("✅ Left security zone: %s", zone["name"])
                    del self.zone_entry_time[zid]
                if zid in self.alarmed_zones:
                    self.alarmed_zones.remove(zid)

        payload = {
            "status": current_status,
            "zone_id": active_zone["id"] if active_zone else 0,
            "zone_name": zone_name,
            "elapsed": round(elapsed_sec, 1),
            "suspicion_time": suspicion_t,
            "alarm_time": alarm_t,
            "remaining_alarm": round(remaining_alarm, 1)
        }

        self.security_pub.publish(String(data=json.dumps(payload)))

    def reset_callback(self, msg):
        rospy.loginfo("[SECURITY] Resetting security timers and alarms.")
        self.zone_entry_time.clear()
        self.alarmed_zones.clear()


def main():
    try:
        SecurityDetector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
