#!/usr/bin/env python3
"""
Robo Treasure Hunt - Player Controller
- Keyboard control: W (forward), S (backward), A (left), D (right)
- Discrete step execution: moves for a short duration then explicitly commands ZERO velocity
- Shift / Uppercase support for 2.0x Speed Boost:
    Normal: 0.50 m/s linear, 1.4 rad/s angular
    Boost:  0.90 m/s linear, 2.0 rad/s angular
- Publishes /game/speed_mode ("1.0x" or "2.0x")
- Respects movement lock when /game/state is GAME_FAILED or MISSION_COMPLETE
- Key 'R' triggers /game/reset
- Clean terminal restoration on exit
"""

import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Empty
import sys
import termios
import tty
import select
import yaml

# Default Speeds
NORMAL_LINEAR = 0.50
BOOST_LINEAR = 0.90
NORMAL_ANGULAR = 1.40
BOOST_ANGULAR = 2.00
MOVE_TIME = 0.30
TURN_TIME = 0.20


def get_key(timeout=0.1):
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            key = sys.stdin.read(1)
            return key
        return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class PlayerController:
    def __init__(self):
        rospy.init_node("player_controller")

        # Load game config if available
        game_file = rospy.get_param("~game_file", "")
        global NORMAL_LINEAR, BOOST_LINEAR, NORMAL_ANGULAR, BOOST_ANGULAR, MOVE_TIME, TURN_TIME
        if game_file:
            try:
                with open(game_file, "r") as f:
                    cfg = yaml.safe_load(f).get("player", {})
                    NORMAL_LINEAR = cfg.get("normal_linear_speed", NORMAL_LINEAR)
                    BOOST_LINEAR = cfg.get("boost_linear_speed", BOOST_LINEAR)
                    NORMAL_ANGULAR = cfg.get("normal_angular_speed", NORMAL_ANGULAR)
                    BOOST_ANGULAR = cfg.get("boost_angular_speed", BOOST_ANGULAR)
                    MOVE_TIME = cfg.get("move_time", MOVE_TIME)
                    TURN_TIME = cfg.get("turn_time", TURN_TIME)
            except Exception as e:
                rospy.logwarn("[PLAYER] Could not load game.yaml: %s", e)

        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
        self.reset_pub = rospy.Publisher("/game/reset", Empty, queue_size=10)
        self.speed_pub = rospy.Publisher("/game/speed_mode", String, queue_size=10, latch=True)

        self.game_state = "PLAYING"
        rospy.Subscriber("/game/state", String, self.state_callback)

        self.speed_mode = "1.0x"
        self.speed_pub.publish(String(data=self.speed_mode))

        self.print_instructions()

    def state_callback(self, msg):
        self.game_state = msg.data

    def print_instructions(self):
        print("\n" + "=" * 48)
        print("          ROBO TREASURE HUNT - PLAYER")
        print("=" * 48)
        print(" CONTROLS:")
        print("   W / S       : Move Forward / Backward (step)")
        print("   A / D       : Turn Left / Right (step)")
        print("   SHIFT + KEY : 2.0x SPEED BOOST (uppercase)")
        print("   R           : Reset / Replay Mission")
        print("   Q           : Quit Controller")
        print("-" * 48)
        print(f" Normal Speed : {NORMAL_LINEAR:.2f} m/s, Turn: {NORMAL_ANGULAR:.2f} rad/s")
        print(f" Boost Speed  : {BOOST_LINEAR:.2f} m/s, Turn: {BOOST_ANGULAR:.2f} rad/s")
        print("=" * 48 + "\n")

    def execute_discrete_move(self, linear, angular, duration):
        """Executes a single discrete step and then reliably publishes zero twist."""
        cmd = Twist()
        cmd.linear.x = linear
        cmd.angular.z = angular

        start_time = rospy.Time.now()
        rate = rospy.Rate(40)

        while not rospy.is_shutdown():
            elapsed = (rospy.Time.now() - start_time).to_sec()
            if elapsed >= duration or self.game_state in ["GAME_FAILED", "MISSION_COMPLETE"]:
                break
            self.cmd_pub.publish(cmd)
            rate.sleep()

        # Stop robot completely
        self.cmd_pub.publish(Twist())

    def run(self):
        rate = rospy.Rate(50)

        while not rospy.is_shutdown():
            key = get_key(timeout=0.05)
            if not key:
                rate.sleep()
                continue

            # Quit
            if key in ['q', 'Q']:
                rospy.loginfo("[PLAYER] Quitting player controller.")
                break

            # Reset / Replay
            if key in ['r', 'R']:
                rospy.loginfo("[PLAYER] 'R' pressed. Sending mission reset signal.")
                self.reset_pub.publish(Empty())
                rate.sleep()
                continue

            # Check movement lock
            if self.game_state in ["GAME_FAILED", "MISSION_COMPLETE"]:
                # Movement disabled
                rate.sleep()
                continue

            # Boost detection (uppercase W, S, A, D)
            boost = (key in ['W', 'S', 'A', 'D'])
            new_speed_mode = "2.0x" if boost else "1.0x"
            if new_speed_mode != self.speed_mode:
                self.speed_mode = new_speed_mode
                self.speed_pub.publish(String(data=self.speed_mode))

            k = key.lower()

            if k == 'w':
                lin = BOOST_LINEAR if boost else NORMAL_LINEAR
                self.execute_discrete_move(lin, 0.0, MOVE_TIME)
            elif k == 's':
                lin = BOOST_LINEAR if boost else NORMAL_LINEAR
                self.execute_discrete_move(-lin, 0.0, MOVE_TIME)
            elif k == 'a':
                ang = BOOST_ANGULAR if boost else NORMAL_ANGULAR
                self.execute_discrete_move(0.0, ang, TURN_TIME)
            elif k == 'd':
                ang = BOOST_ANGULAR if boost else NORMAL_ANGULAR
                self.execute_discrete_move(0.0, -ang, TURN_TIME)

            rate.sleep()

        # Ensure robot is stopped on exit
        self.cmd_pub.publish(Twist())


def main():
    try:
        controller = PlayerController()
        controller.run()
    except rospy.ROSInterruptException:
        pass


if __name__ == "__main__":
    main()
