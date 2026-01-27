"""
Shared types, constants, and protocls for RUKA MG996R.

This module contains shared definitions used across multiple components
"""

from ruka_mg996r.shared.constants import (
    DEFAULT_PORT,
    DEFAULT_UPDATE_RATE_HZ,
    FINGER_NAMES,
    JOINT_CHANNELS,
    NUM_CHANNELS,
)

__all__ = [
    # Constants
    "DEFAULT_PORT",
    "DEFAULT_UPDATE_RATE_HZ",
    "FINGER_NAMES",
    "JOINT_CHANNELS",
    "NUM_CHANNELS",
]
