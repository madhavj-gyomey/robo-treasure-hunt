#!/usr/bin/env python3
"""
Robo Treasure Hunt - Graphical Game HUD (PyQt5)
High-readability, crisp stealth HUD with scalable layout, clear typography,
and zero CSS inheritance issues.
"""

import sys
import json
import math
import numpy as np

import rospy
from std_msgs.msg import String, Int32, Empty
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QStackedWidget
)
from PyQt5.QtGui import QFont, QColor, QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject


class RosBridge(QObject):
    state_signal = pyqtSignal(str)
    score_signal = pyqtSignal(int)
    treasures_signal = pyqtSignal(dict)
    security_signal = pyqtSignal(dict)
    speed_signal = pyqtSignal(str)
    image_signal = pyqtSignal(np.ndarray, str)
    event_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        rospy.Subscriber("/game/state", String, self.state_cb)
        rospy.Subscriber("/game/score", Int32, self.score_cb)
        rospy.Subscriber("/game/treasures", String, self.treasures_cb)
        rospy.Subscriber("/game/security", String, self.security_cb)
        rospy.Subscriber("/game/speed_mode", String, self.speed_cb)
        rospy.Subscriber("/game/treasure_event", String, self.event_cb)
        rospy.Subscriber("/camera/image_raw", Image, self.image_cb, queue_size=1)

        self.reset_pub = rospy.Publisher("/game/reset", Empty, queue_size=10)
        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
        self.speed_pub = rospy.Publisher("/game/speed_mode", String, queue_size=10, latch=True)

    def state_cb(self, msg):
        self.state_signal.emit(msg.data)

    def score_cb(self, msg):
        self.score_signal.emit(msg.data)

    def treasures_cb(self, msg):
        try:
            data = json.loads(msg.data)
            self.treasures_signal.emit(data)
        except Exception:
            pass

    def security_cb(self, msg):
        try:
            data = json.loads(msg.data)
            self.security_signal.emit(data)
        except Exception:
            pass

    def speed_cb(self, msg):
        self.speed_signal.emit(msg.data)

    def event_cb(self, msg):
        self.event_signal.emit(msg.data)

    def image_cb(self, msg):
        try:
            h, w = msg.height, msg.width
            encoding = msg.encoding
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, -1))
            self.image_signal.emit(arr, encoding)
        except Exception:
            pass

    def send_reset(self):
        self.reset_pub.publish(Empty())

    def send_move(self, linear, angular):
        cmd = Twist()
        cmd.linear.x = linear
        cmd.angular.z = angular
        self.cmd_pub.publish(cmd)

    def set_speed_mode(self, mode):
        self.speed_pub.publish(String(data=mode))


class GameHudWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROBO TREASURE HUNT - Stealth Thief HUD")
        self.setMinimumSize(1000, 680)
        self.resize(1120, 740)

        # Game State
        self.game_state = "LOADING"
        self.score = 0
        self.speed_mode = "1.0x"
        self.collected_count = 0
        self.total_treasures = 3
        self.banner_timer = 0
        self.banner_text = ""
        self.moving = False

        # Setup ROS Bridge
        self.bridge = RosBridge()
        self.bridge.state_signal.connect(self.on_state)
        self.bridge.score_signal.connect(self.on_score)
        self.bridge.treasures_signal.connect(self.on_treasures)
        self.bridge.security_signal.connect(self.on_security)
        self.bridge.speed_signal.connect(self.on_speed)
        self.bridge.image_signal.connect(self.on_image)
        self.bridge.event_signal.connect(self.on_event)

        # Main UI Stack
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.stack = QStackedWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.stack)

        self.apply_global_style()

        self.init_loading_ui()
        self.init_gameplay_ui()
        self.init_overlay_ui()

        # Loading screen timer
        self.loading_progress = 0
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self.update_loading)
        self.loading_timer.start(70)

        # Banner countdown timer
        self.hud_timer = QTimer(self)
        self.hud_timer.timeout.connect(self.update_hud_tick)
        self.hud_timer.start(100)

    def apply_global_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0d14;
            }
            QWidget {
                color: #f1f5f9;
                font-family: 'DejaVu Sans', 'Ubuntu', 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
            QFrame#card_score, QFrame#card_treasures, QFrame#card_security, QFrame#card_camera {
                background-color: #141724;
                border: 2px solid #23283e;
                border-radius: 10px;
                padding: 14px;
            }
            QFrame#card_radar {
                background-color: #131b2e;
                border: 2px solid #2563eb;
                border-radius: 10px;
                padding: 14px;
            }
            QFrame#fail_box {
                background-color: #1e0808;
                border: 3px solid #dc2626;
                border-radius: 16px;
                padding: 30px;
            }
            QFrame#win_box {
                background-color: #042417;
                border: 3px solid #059669;
                border-radius: 16px;
                padding: 30px;
            }
        """)

    # ----------------------------------------------------
    # LOADING SCREEN UI
    # ----------------------------------------------------
    def init_loading_ui(self):
        self.loading_page = QWidget()
        layout = QVBoxLayout(self.loading_page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(18)

        title = QLabel("ROBO TREASURE HUNT")
        title.setFont(QFont("Arial", 32, QFont.Bold))
        title.setStyleSheet("color: #38bdf8;")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("STEALTH ROBOT INFILTRATION")
        subtitle.setFont(QFont("Arial", 13, QFont.Bold))
        subtitle.setStyleSheet("color: #94a3b8;")
        subtitle.setAlignment(Qt.AlignCenter)

        self.loading_status_lbl = QLabel("INITIALIZING MISSION...")
        self.loading_status_lbl.setFont(QFont("Arial", 16, QFont.Bold))
        self.loading_status_lbl.setStyleSheet("color: #fbbf24;")
        self.loading_status_lbl.setAlignment(Qt.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(540, 26)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 13px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
                border-radius: 12px;
            }
        """)
        self.progress_bar.setValue(0)

        self.loading_step_lbl = QLabel("Loading museum architecture & navigation mesh...")
        self.loading_step_lbl.setFont(QFont("Arial", 12))
        self.loading_step_lbl.setStyleSheet("color: #64748b;")
        self.loading_step_lbl.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(25)
        layout.addWidget(self.loading_status_lbl)
        layout.addWidget(self.progress_bar, 0, Qt.AlignCenter)
        layout.addWidget(self.loading_step_lbl)
        layout.addStretch()

        self.stack.addWidget(self.loading_page)

    def update_loading(self):
        self.loading_progress += 4

        if self.loading_progress < 30:
            self.loading_step_lbl.setText("Loading museum architecture & corridors...")
        elif self.loading_progress < 60:
            self.loading_step_lbl.setText("Calibrating security laser detection zones...")
        elif self.loading_progress < 85:
            self.loading_step_lbl.setText("Positioning Golden Idol, Ancient Gem & Royal Crown...")
        else:
            self.loading_step_lbl.setText("Connecting TurtleBot3 Burger camera & LiDAR...")

        self.progress_bar.setValue(min(self.loading_progress, 100))

        if self.loading_progress >= 100:
            self.loading_timer.stop()
            self.loading_status_lbl.setText("MISSION READY")
            self.loading_status_lbl.setStyleSheet("color: #34d399;")
            QTimer.singleShot(500, self.start_gameplay)

    def start_gameplay(self):
        if self.game_state not in ["GAME_FAILED", "MISSION_COMPLETE"]:
            self.stack.setCurrentIndex(1)
            self.game_state = "PLAYING"

    # ----------------------------------------------------
    # MAIN GAMEPLAY UI
    # ----------------------------------------------------
    def init_gameplay_ui(self):
        self.gameplay_page = QWidget()
        main_layout = QVBoxLayout(self.gameplay_page)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        # 1. Header Bar
        header = QHBoxLayout()
        title = QLabel("ROBO TREASURE HUNT")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #38bdf8;")

        self.speed_badge = QLabel("SPEED 1.0x")
        self.speed_badge.setFont(QFont("Arial", 12, QFont.Bold))
        self.speed_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            border: 2px solid #0284c7;
            border-radius: 6px;
            padding: 6px 14px;
        """)

        self.mission_status_lbl = QLabel("MISSION: IN PROGRESS")
        self.mission_status_lbl.setFont(QFont("Arial", 12, QFont.Bold))
        self.mission_status_lbl.setStyleSheet("color: #34d399; padding: 6px 10px;")

        self.reset_btn = QPushButton("↺ RESET (R)")
        self.reset_btn.setFont(QFont("Arial", 11, QFont.Bold))
        self.reset_btn.setFocusPolicy(Qt.NoFocus)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                border: 2px solid #475569;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.reset_btn.clicked.connect(self.on_reset_clicked)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.speed_badge)
        header.addSpacing(12)
        header.addWidget(self.mission_status_lbl)
        header.addSpacing(16)
        header.addWidget(self.reset_btn)
        main_layout.addLayout(header)

        # 2. Notification Banner (Popup for +100 STOLEN)
        self.banner_lbl = QLabel("")
        self.banner_lbl.setFont(QFont("Arial", 14, QFont.Bold))
        self.banner_lbl.setAlignment(Qt.AlignCenter)
        self.banner_lbl.setStyleSheet("""
            background-color: #b45309;
            color: #fef08a;
            border-radius: 6px;
            padding: 8px;
        """)
        self.banner_lbl.setFixedHeight(38)
        self.banner_lbl.hide()
        main_layout.addWidget(self.banner_lbl)

        # 3. Main Split View: Left (Stats & Radar) + Right (Camera & Security)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # ---- LEFT PANEL ----
        left_box = QVBoxLayout()
        left_box.setSpacing(14)

        # Score Card
        score_card = QFrame()
        score_card.setObjectName("card_score")
        score_layout = QVBoxLayout(score_card)
        score_title = QLabel("CURRENT SCORE")
        score_title.setFont(QFont("Arial", 11, QFont.Bold))
        score_title.setStyleSheet("color: #94a3b8;")
        self.score_val = QLabel("SCORE: 000")
        self.score_val.setFont(QFont("Arial", 28, QFont.Bold))
        self.score_val.setStyleSheet("color: #facc15;")
        score_layout.addWidget(score_title)
        score_layout.addWidget(self.score_val)
        left_box.addWidget(score_card)

        # Treasures Card
        treasures_card = QFrame()
        treasures_card.setObjectName("card_treasures")
        t_layout = QVBoxLayout(treasures_card)
        t_header = QHBoxLayout()
        t_title = QLabel("MUSEUM TREASURES")
        t_title.setFont(QFont("Arial", 11, QFont.Bold))
        t_title.setStyleSheet("color: #94a3b8;")
        self.t_count_lbl = QLabel("0 / 3")
        self.t_count_lbl.setFont(QFont("Arial", 14, QFont.Bold))
        self.t_count_lbl.setStyleSheet("color: #38bdf8;")
        t_header.addWidget(t_title)
        t_header.addStretch()
        t_header.addWidget(self.t_count_lbl)
        t_layout.addLayout(t_header)

        self.t1_lbl = QLabel("⏳ 1. Golden Idol")
        self.t2_lbl = QLabel("⏳ 2. Ancient Gem")
        self.t3_lbl = QLabel("⏳ 3. Royal Crown")
        for lbl in [self.t1_lbl, self.t2_lbl, self.t3_lbl]:
            lbl.setFont(QFont("Arial", 13, QFont.Bold))
            lbl.setStyleSheet("color: #cbd5e1; margin-top: 4px;")
            t_layout.addWidget(lbl)
        left_box.addWidget(treasures_card)

        # Radar / Direction Indicator Card
        radar_card = QFrame()
        radar_card.setObjectName("card_radar")
        radar_layout = QVBoxLayout(radar_card)
        radar_title = QLabel("NEXT TREASURE RADAR")
        radar_title.setFont(QFont("Arial", 11, QFont.Bold))
        radar_title.setStyleSheet("color: #60a5fa;")

        self.radar_name_lbl = QLabel("Ancient Gem")
        self.radar_name_lbl.setFont(QFont("Arial", 15, QFont.Bold))
        self.radar_name_lbl.setStyleSheet("color: #ffffff;")

        radar_display = QHBoxLayout()
        self.radar_arrow_lbl = QLabel("↑")
        self.radar_arrow_lbl.setFont(QFont("Arial", 44, QFont.Bold))
        self.radar_arrow_lbl.setStyleSheet("color: #38bdf8;")
        self.radar_arrow_lbl.setAlignment(Qt.AlignCenter)
        self.radar_dist_lbl = QLabel("Distance: 7.0 m")
        self.radar_dist_lbl.setFont(QFont("Arial", 14, QFont.Bold))
        self.radar_dist_lbl.setStyleSheet("color: #94a3b8;")

        radar_display.addWidget(self.radar_arrow_lbl)
        radar_display.addSpacing(14)
        radar_display.addWidget(self.radar_dist_lbl)
        radar_display.addStretch()

        radar_layout.addWidget(radar_title)
        radar_layout.addWidget(self.radar_name_lbl)
        radar_layout.addLayout(radar_display)
        left_box.addWidget(radar_card)

        left_box.addStretch()
        content_layout.addLayout(left_box, 1)

        # ---- RIGHT PANEL ----
        right_box = QVBoxLayout()
        right_box.setSpacing(14)

        # Security Status Card
        sec_card = QFrame()
        sec_card.setObjectName("card_security")
        sec_layout = QVBoxLayout(sec_card)
        sec_header = QHBoxLayout()
        sec_title = QLabel("SECURITY SYSTEM")
        sec_title.setFont(QFont("Arial", 11, QFont.Bold))
        sec_title.setStyleSheet("color: #94a3b8;")

        self.sec_status_badge = QLabel("CLEAR")
        self.sec_status_badge.setFont(QFont("Arial", 12, QFont.Bold))
        self.sec_status_badge.setStyleSheet("""
            background-color: #064e3b;
            color: #34d399;
            border: 2px solid #059669;
            border-radius: 6px;
            padding: 4px 12px;
        """)
        sec_header.addWidget(sec_title)
        sec_header.addStretch()
        sec_header.addWidget(self.sec_status_badge)
        sec_layout.addLayout(sec_header)

        self.sec_detail_lbl = QLabel("All zones clear. Infiltration stealth intact.")
        self.sec_detail_lbl.setFont(QFont("Arial", 12))
        self.sec_detail_lbl.setStyleSheet("color: #94a3b8; margin-top: 4px;")
        sec_layout.addWidget(self.sec_detail_lbl)
        right_box.addWidget(sec_card)

        # FPV Camera Viewport Card
        cam_card = QFrame()
        cam_card.setObjectName("card_camera")
        cam_layout = QVBoxLayout(cam_card)
        cam_header = QHBoxLayout()
        cam_title = QLabel("TURTLEBOT FPV CAMERA (/camera/image_raw)")
        cam_title.setFont(QFont("Arial", 11, QFont.Bold))
        cam_title.setStyleSheet("color: #94a3b8;")
        cam_header.addWidget(cam_title)
        cam_header.addStretch()
        cam_layout.addLayout(cam_header)

        self.cam_viewport = QLabel()
        self.cam_viewport.setMinimumSize(420, 260)
        self.cam_viewport.setStyleSheet("""
            background-color: #05060a;
            border: 2px solid #1e293b;
            border-radius: 6px;
            color: #64748b;
            font-size: 13px;
        """)
        self.cam_viewport.setAlignment(Qt.AlignCenter)
        self.cam_viewport.setText("SENSOR STANDBY / SCANNING...")
        cam_layout.addWidget(self.cam_viewport)
        right_box.addWidget(cam_card, 1)

        content_layout.addLayout(right_box, 1)
        main_layout.addLayout(content_layout)

        # 4. Controls Cheatsheet Bar
        controls_bar = QLabel("⌨ CONTROLS: W/A/S/D = Discrete Move | SHIFT + KEY = 2.0x Speed Boost | R = Reset / Replay | Q = Quit")
        controls_bar.setFont(QFont("Arial", 11, QFont.Bold))
        controls_bar.setStyleSheet("color: #64748b; padding-top: 6px;")
        controls_bar.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(controls_bar)

        self.stack.addWidget(self.gameplay_page)

    # ----------------------------------------------------
    # OVERLAYS (Game Failed / Mission Complete)
    # ----------------------------------------------------
    def init_overlay_ui(self):
        # 1. Game Failed Page
        self.fail_page = QWidget()
        fail_outer = QVBoxLayout(self.fail_page)
        fail_outer.setAlignment(Qt.AlignCenter)

        fail_box = QFrame()
        fail_box.setObjectName("fail_box")
        fail_box.setFixedSize(620, 420)
        fb_layout = QVBoxLayout(fail_box)
        fb_layout.setAlignment(Qt.AlignCenter)
        fb_layout.setSpacing(14)

        f_title = QLabel("GAME FAILED")
        f_title.setFont(QFont("Arial", 36, QFont.Bold))
        f_title.setStyleSheet("color: #ff3333;")
        f_title.setAlignment(Qt.AlignCenter)

        f_sub = QLabel("SECURITY INTRUDER DETECTED")
        f_sub.setFont(QFont("Arial", 15, QFont.Bold))
        f_sub.setStyleSheet("color: #fca5a5;")
        f_sub.setAlignment(Qt.AlignCenter)

        self.fail_score_lbl = QLabel("SCORE: 000")
        self.fail_score_lbl.setFont(QFont("Arial", 22, QFont.Bold))
        self.fail_score_lbl.setStyleSheet("color: #fde047;")
        self.fail_score_lbl.setAlignment(Qt.AlignCenter)

        self.fail_t_lbl = QLabel("TREASURES COLLECTED: 0 / 3")
        self.fail_t_lbl.setFont(QFont("Arial", 15, QFont.Bold))
        self.fail_t_lbl.setStyleSheet("color: #f8fafc;")
        self.fail_t_lbl.setAlignment(Qt.AlignCenter)

        retry_btn = QPushButton("↺ PRESS R TO RETRY")
        retry_btn.setFont(QFont("Arial", 15, QFont.Bold))
        retry_btn.setFixedSize(300, 52)
        retry_btn.setCursor(Qt.PointingHandCursor)
        retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                border: 2px solid #ef4444;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        retry_btn.clicked.connect(self.on_reset_clicked)

        fb_layout.addWidget(f_title)
        fb_layout.addWidget(f_sub)
        fb_layout.addSpacing(8)
        fb_layout.addWidget(self.fail_score_lbl)
        fb_layout.addWidget(self.fail_t_lbl)
        fb_layout.addSpacing(16)
        fb_layout.addWidget(retry_btn, 0, Qt.AlignCenter)

        fail_outer.addWidget(fail_box, 0, Qt.AlignCenter)
        self.stack.addWidget(self.fail_page)

        # 2. Mission Complete Page
        self.win_page = QWidget()
        win_outer = QVBoxLayout(self.win_page)
        win_outer.setAlignment(Qt.AlignCenter)

        win_box = QFrame()
        win_box.setObjectName("win_box")
        win_box.setFixedSize(620, 420)
        wb_layout = QVBoxLayout(win_box)
        wb_layout.setAlignment(Qt.AlignCenter)
        wb_layout.setSpacing(14)

        w_title = QLabel("MISSION COMPLETE")
        w_title.setFont(QFont("Arial", 36, QFont.Bold))
        w_title.setStyleSheet("color: #10b981;")
        w_title.setAlignment(Qt.AlignCenter)

        w_sub = QLabel("ALL TREASURES STOLEN")
        w_sub.setFont(QFont("Arial", 15, QFont.Bold))
        w_sub.setStyleSheet("color: #6ee7b7;")
        w_sub.setAlignment(Qt.AlignCenter)

        self.win_score_lbl = QLabel("SCORE: 300")
        self.win_score_lbl.setFont(QFont("Arial", 24, QFont.Bold))
        self.win_score_lbl.setStyleSheet("color: #fde047;")
        self.win_score_lbl.setAlignment(Qt.AlignCenter)

        w_count = QLabel("ARTIFACTS SECURED: 3 / 3")
        w_count.setFont(QFont("Arial", 15, QFont.Bold))
        w_count.setStyleSheet("color: #f8fafc;")
        w_count.setAlignment(Qt.AlignCenter)

        replay_btn = QPushButton("↺ PRESS R TO REPLAY")
        replay_btn.setFont(QFont("Arial", 15, QFont.Bold))
        replay_btn.setFixedSize(300, 52)
        replay_btn.setCursor(Qt.PointingHandCursor)
        replay_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                border: 2px solid #10b981;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        replay_btn.clicked.connect(self.on_reset_clicked)

        wb_layout.addWidget(w_title)
        wb_layout.addWidget(w_sub)
        wb_layout.addSpacing(8)
        wb_layout.addWidget(self.win_score_lbl)
        wb_layout.addWidget(w_count)
        wb_layout.addSpacing(16)
        wb_layout.addWidget(replay_btn, 0, Qt.AlignCenter)

        win_outer.addWidget(win_box, 0, Qt.AlignCenter)
        self.stack.addWidget(self.win_page)

    # ----------------------------------------------------
    # SLOTS & CALLBACKS
    # ----------------------------------------------------
    def on_state(self, state):
        self.game_state = state

        if state == "GAME_FAILED":
            self.fail_score_lbl.setText(f"FINAL SCORE: {self.score:03d}")
            self.fail_t_lbl.setText(f"TREASURES COLLECTED: {self.collected_count} / {self.total_treasures}")
            self.stack.setCurrentIndex(2)  # fail page
        elif state == "MISSION_COMPLETE":
            self.win_score_lbl.setText(f"FINAL SCORE: {self.score:03d}")
            self.stack.setCurrentIndex(3)  # win page
        elif state in ["PLAYING", "SUSPICIOUS", "RESETTING"]:
            if self.stack.currentIndex() not in [0, 1]:
                self.stack.setCurrentIndex(1)  # back to gameplay
            self.mission_status_lbl.setText(f"MISSION: {state}")
            if state == "PLAYING":
                self.mission_status_lbl.setStyleSheet("color: #34d399; padding: 6px 10px;")
            elif state == "SUSPICIOUS":
                self.mission_status_lbl.setStyleSheet("color: #fbbf24; padding: 6px 10px;")

    def on_score(self, score):
        self.score = score
        self.score_val.setText(f"SCORE: {self.score:03d}")

    def on_treasures(self, data):
        self.total_treasures = data.get("total", 3)
        self.collected_count = data.get("collected", 0)
        self.t_count_lbl.setText(f"{self.collected_count} / {self.total_treasures}")

        # Checklist
        items = data.get("treasures", [])
        if len(items) >= 3:
            s1 = "✔" if items[0]["collected"] else "⏳"
            s2 = "✔" if items[1]["collected"] else "⏳"
            s3 = "✔" if items[2]["collected"] else "⏳"
            c1 = "#34d399" if items[0]["collected"] else "#cbd5e1"
            c2 = "#34d399" if items[1]["collected"] else "#cbd5e1"
            c3 = "#34d399" if items[2]["collected"] else "#cbd5e1"
            self.t1_lbl.setText(f"{s1} 1. {items[0]['name']}")
            self.t2_lbl.setText(f"{s2} 2. {items[1]['name']}")
            self.t3_lbl.setText(f"{s3} 3. {items[2]['name']}")
            self.t1_lbl.setStyleSheet(f"color: {c1}; margin-top: 4px;")
            self.t2_lbl.setStyleSheet(f"color: {c2}; margin-top: 4px;")
            self.t3_lbl.setStyleSheet(f"color: {c3}; margin-top: 4px;")

        # Radar
        if data.get("all_collected", False):
            self.radar_name_lbl.setText("ALL TREASURES COLLECTED!")
            self.radar_arrow_lbl.setText("★")
            self.radar_arrow_lbl.setStyleSheet("color: #facc15;")
            self.radar_dist_lbl.setText("Head to Museum Exit")
        else:
            self.radar_name_lbl.setText(f"{data.get('nearest_name', 'Unknown')}")
            arrow = data.get("nearest_arrow", "↑")
            self.radar_arrow_lbl.setText(arrow)
            self.radar_arrow_lbl.setStyleSheet("color: #38bdf8;")
            self.radar_dist_lbl.setText(f"Distance: {data.get('nearest_dist', 0.0):.1f} m")

    def on_security(self, data):
        status = data.get("status", "CLEAR")
        zone_name = data.get("zone_name", "None")
        elapsed = data.get("elapsed", 0.0)
        rem_alarm = data.get("remaining_alarm", 0.0)

        if status == "ALARM":
            self.sec_status_badge.setText("ALARM")
            self.sec_status_badge.setStyleSheet("""
                background-color: #7f1d1d;
                color: #f87171;
                border: 2px solid #ef4444;
                border-radius: 6px;
                padding: 4px 12px;
            """)
            self.sec_detail_lbl.setText(f"🚨 ALARM in {zone_name}! INTRUDER DETECTED!")
            self.sec_detail_lbl.setStyleSheet("color: #fca5a5; font-weight: bold; margin-top: 4px;")
        elif status == "SUSPICIOUS":
            self.sec_status_badge.setText(f"SUSPICIOUS ({rem_alarm:.1f}s)")
            self.sec_status_badge.setStyleSheet("""
                background-color: #78350f;
                color: #fde047;
                border: 2px solid #eab308;
                border-radius: 6px;
                padding: 4px 12px;
            """)
            self.sec_detail_lbl.setText(f"⚠️ Warning: Inside {zone_name}. Escape in {rem_alarm:.1f}s!")
            self.sec_detail_lbl.setStyleSheet("color: #fde047; margin-top: 4px;")
        else:
            self.sec_status_badge.setText("CLEAR")
            self.sec_status_badge.setStyleSheet("""
                background-color: #064e3b;
                color: #34d399;
                border: 2px solid #059669;
                border-radius: 6px;
                padding: 4px 12px;
            """)
            self.sec_detail_lbl.setText("All zones clear. Infiltration stealth intact.")
            self.sec_detail_lbl.setStyleSheet("color: #94a3b8; margin-top: 4px;")

    def on_speed(self, speed_str):
        self.speed_mode = speed_str
        self.speed_badge.setText(f"SPEED {speed_str}")
        if "2.0" in speed_str:
            self.speed_badge.setStyleSheet("""
                background-color: #1e1b4b;
                color: #c084fc;
                border: 2px solid #9333ea;
                border-radius: 6px;
                padding: 6px 14px;
            """)
        else:
            self.speed_badge.setStyleSheet("""
                background-color: #1e293b;
                color: #38bdf8;
                border: 2px solid #0284c7;
                border-radius: 6px;
                padding: 6px 14px;
            """)

    def on_event(self, event_str):
        try:
            parts = event_str.split(":")
            if parts[0] == "COLLECTED" and len(parts) >= 3:
                name = parts[2]
                self.banner_text = f"💰 +100 TREASURE STOLEN: {name.upper()}"
                self.banner_lbl.setText(self.banner_text)
                self.banner_lbl.show()
                self.banner_timer = 20  # 2.0 seconds at 10 Hz
        except Exception:
            pass

    def on_image(self, arr, encoding):
        try:
            h, w, c = arr.shape
            if encoding == "rgb8":
                qimg = QImage(arr.data, w, h, w * c, QImage.Format_RGB888)
            else:  # bgr8 default
                qimg = QImage(arr.data, w, h, w * c, QImage.Format_BGR888)

            pixmap = QPixmap.fromImage(qimg).scaled(
                self.cam_viewport.width(),
                self.cam_viewport.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.cam_viewport.setPixmap(pixmap)
        except Exception:
            pass

    def update_hud_tick(self):
        if self.banner_timer > 0:
            self.banner_timer -= 1
            if self.banner_timer == 0:
                self.banner_lbl.hide()

    def execute_hud_move(self, linear, angular, duration_sec):
        if self.moving:
            return
        self.moving = True
        self.bridge.send_move(linear, angular)
        QTimer.singleShot(int(duration_sec * 1000), self.stop_hud_move)

    def stop_hud_move(self):
        self.bridge.send_move(0.0, 0.0)
        self.moving = False

    def on_reset_clicked(self):
        rospy.loginfo("[HUD] Reset triggered.")
        self.bridge.send_reset()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        boost = bool(modifiers & Qt.ShiftModifier)

        if key == Qt.Key_R:
            self.on_reset_clicked()
        elif key == Qt.Key_Q:
            self.close()
        elif self.game_state not in ["GAME_FAILED", "MISSION_COMPLETE"]:
            lin = 0.90 if boost else 0.50
            ang = 2.00 if boost else 1.40
            new_mode = "2.0x" if boost else "1.0x"
            if new_mode != self.speed_mode:
                self.speed_mode = new_mode
                self.bridge.set_speed_mode(self.speed_mode)

            if key == Qt.Key_W:
                self.execute_hud_move(lin, 0.0, 0.30)
            elif key == Qt.Key_S:
                self.execute_hud_move(-lin, 0.0, 0.30)
            elif key == Qt.Key_A:
                self.execute_hud_move(0.0, ang, 0.20)
            elif key == Qt.Key_D:
                self.execute_hud_move(0.0, -ang, 0.20)
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


def main():
    rospy.init_node("game_hud", anonymous=False)
    app = QApplication(sys.argv)
    window = GameHudWindow()
    window.show()

    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
