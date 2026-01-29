"""
Constants for RUKA MG996R project.

This module defines all shared constants used across the RUKA MG996R package.
NOTE: Adjust these constants if you have a different wiring setup or servo model.
"""

# ====================================================================================
# Network Config
# ====================================================================================

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_WS_PATH = "/ws/control"

# ====================================================================================
# Servo Config
# ====================================================================================

NUM_CHANNELS = 11  # Total number of servo channels (0-10)

# NOTE: All of these assume you wired the servos in this exact order, adjust if needed.
# Channel to joint name mapping
JOINT_NAMES: dict[int, str] = {
    0: "pinky_mcp",
    1: "pinky_pip",
    2: "ring_mcp",
    3: "ring_pip",
    4: "middle_mcp",
    5: "middle_pip",
    6: "index_mcp",
    7: "index_pip",
    8: "thumb_cmc",
    9: "thumb_mcp",
    10: "thumb_ip",
}
# Finger name to channel mapping
JOINT_CHANNELS: dict[str, list[int]] = {
    "pinky": [0, 1],
    "ring": [2, 3],
    "middle": [4, 5],
    "index": [6, 7],
    "thumb": [8, 9, 10],
}
FINGER_CHANNELS: set = {0, 1, 2, 3, 4, 5, 6, 7}
THUMB_CHANNELS: set = {8, 9, 10}

# List of all finger names in order
FINGER_NAMES: list[str] = ["pinky", "ring", "middle", "index", "thumb"]

# ====================================================================================
# MG996R Servo Specs
# ====================================================================================

# Safe pulse width range for MG996R servos (in microseconds)
MG996R_SAFE_PULSE_MIN = 500
MG996R_SAFE_PULSE_MAX = 2500

# Default pulse range if no calibration exists
DEFAULT_PULSE_MIN = 500
DEFAULT_PULSE_MAX = 2500
DEFAULT_PULSE_CENTER = (DEFAULT_PULSE_MIN + DEFAULT_PULSE_MAX) // 2

# ====================================================================================
# Control Parameters
# ====================================================================================

DEFAULT_UPDATE_RATE_HZ = 50.0
DEFAULT_SMOOTHING_FACTOR = 0.15  # Exponential smoothing (0.05-0.5)
DEFAULT_MAX_VELOCITY = 300.0  # Max degrees per second

# Motion planning defaults
DEFAULT_TRAJECTORY_DURATION = 0.25  # seconds
MIN_TRAJECTORY_DURATION = 0.1
MAX_TRAJECTORY_DURATION = 1.0

# Latency Compensation
DEFAULT_LATENCY_MS = 50.0
MAX_ACCEPTABLE_LATENCY_MS = 250.0

# ====================================================================================
# MediaPipe Landmark Indices
# ====================================================================================

LANDMARK_WRIST = 0
# Thumb
LANDMARK_THUMB_CMC = 1
LANDMARK_THUMB_MCP = 2
LANDMARK_THUMB_IP = 3
LANDMARK_THUMB_TIP = 4
# Index
LANDMARK_INDEX_MCP = 5
LANDMARK_INDEX_PIP = 6
LANDMARK_INDEX_DIP = 7
LANDMARK_INDEX_TIP = 8
# Middle
LANDMARK_MIDDLE_MCP = 9
LANDMARK_MIDDLE_PIP = 10
LANDMARK_MIDDLE_DIP = 11
LANDMARK_MIDDLE_TIP = 12
# Ring
LANDMARK_RING_MCP = 13
LANDMARK_RING_PIP = 14
LANDMARK_RING_DIP = 15
LANDMARK_RING_TIP = 16
# Pinky
LANDMARK_PINKY_MCP = 17
LANDMARK_PINKY_PIP = 18
LANDMARK_PINKY_DIP = 19
LANDMARK_PINKY_TIP = 20

NUM_LANDMARKS = 21

# ===================================================================================
# File Paths
# ====================================================================================

DEFAULT_CALIBRATION_PATH = "data/calibration/mg996r_calibration.json"
