"""
Pytest fixtures for RUKA MG996R tests.

Provides common fixtures for testing server components.
Fixtures dynamically use the project's actual constants to ensure
tests match your specific configuration.
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Import project constants to accurately reflect configuration
from ruka_mg996r.shared.constants import (
    DEFAULT_PULSE_MAX,
    DEFAULT_PULSE_MIN,
    FINGER_CHANNELS,
    JOINT_NAMES,
    NUM_CHANNELS,
    THUMB_CHANNELS,
)

# =============================================================================
# Dynamic Calibration Data Generators
# =============================================================================


def make_servo_calibration(
    channel: int,
    calibrated: bool = True,
    pulse_min: int = DEFAULT_PULSE_MIN,
    pulse_max: int = DEFAULT_PULSE_MAX,
) -> dict:
    """
    Create servo calibration dict for a channel using project constants.

    Args:
        channel: Channel number
        calibrated: Whether to include operational positions
        pulse_min: Override pulse min (default: varies by channel)
        pulse_max: Override pulse max (default: varies by channel)
    """
    joint_name = JOINT_NAMES.get(channel, f"channel_{channel}")
    is_thumb = channel in THUMB_CHANNELS

    # Vary pulse ranges slightly by channel for realistic data
    p_min = pulse_min if pulse_min is not None else (700 + channel * 10)
    p_max = pulse_max if pulse_max is not None else (2200 - channel * 10)

    data = {
        "channel": channel,
        "joint_name": joint_name,
        "pulse_min": p_min,
        "pulse_max": p_max,
        "curl_direction_positive": not is_thumb,  # Thumb reversed
    }

    if calibrated:
        if is_thumb:
            # Thumb: high pulse = open (slack), low pulse = curled
            data["slack_pulse"] = p_max - 100
            data["taut_pulse"] = p_max - 200
            data["curled_pulse"] = p_min + 200
        else:
            # Finger: low pulse = open (slack), high pulse = curled
            data["slack_pulse"] = p_min + 50
            data["taut_pulse"] = p_min + 150
            data["curled_pulse"] = p_max - 200
    else:
        data["slack_pulse"] = None
        data["taut_pulse"] = None
        data["curled_pulse"] = None

    return data


def make_calibration_data(
    channels: list[int] | None = None,
    calibrated: bool = True,
) -> dict:
    """
    Create full calibration data dict using project constants.

    Args:
        channels: List of channels to include (default: all from NUM_CHANNELS)
        calibrated: Whether servos should have operational positions
    """
    if channels is None:
        channels = list(range(NUM_CHANNELS))

    calibrations = {}
    for ch in channels:
        calibrations[str(ch)] = make_servo_calibration(ch, calibrated=calibrated)

    return {
        "servos": calibrations,
        "control_params": {
            "update_rate_hz": 50.0,
            "smoothing_factor": 0.15,
        },
        "metadata": {
            "version": "1.0",
        },
    }


# =============================================================================
# Calibration Data Fixtures
# =============================================================================


@pytest.fixture
def sample_calibration_data():
    """
    Sample calibration data with a subset of channels.
    Uses actual JOINT_NAMES and THUMB_CHANNELS from your constants.
    """
    # Pick a few representative channels (thumb + some fingers)
    thumb_channels = sorted(list(THUMB_CHANNELS))[:2] if THUMB_CHANNELS else []
    finger_channels = sorted(list(FINGER_CHANNELS))[:2] if FINGER_CHANNELS else []
    channels = thumb_channels + finger_channels

    return make_calibration_data(channels=channels, calibrated=True)


@pytest.fixture
def full_calibration_data():
    """
    Full calibration data with all channels from NUM_CHANNELS.
    Uses actual JOINT_NAMES and THUMB_CHANNELS from your constants.
    """
    return make_calibration_data(calibrated=True)


@pytest.fixture
def uncalibrated_data():
    """Calibration data without operational positions set."""
    return make_calibration_data(calibrated=False)


@pytest.fixture
def temp_calibration_file(tmp_path, sample_calibration_data):
    """Create a temporary calibration file with sample data."""
    filepath = tmp_path / "test_calibration.json"
    with open(filepath, "w") as f:
        json.dump(sample_calibration_data, f)
    return filepath


@pytest.fixture
def full_temp_calibration_file(tmp_path, full_calibration_data):
    """Create a temporary calibration file with all channels."""
    filepath = tmp_path / "full_calibration.json"
    with open(filepath, "w") as f:
        json.dump(full_calibration_data, f)
    return filepath


# =============================================================================
# Project Constants Fixtures (for tests that need direct access)
# =============================================================================


@pytest.fixture
def project_joint_names():
    """Access to actual JOINT_NAMES from your constants."""
    return JOINT_NAMES.copy()


@pytest.fixture
def project_thumb_channels():
    """Access to actual THUMB_CHANNELS from your constants."""
    return THUMB_CHANNELS.copy()


@pytest.fixture
def project_finger_channels():
    """Access to actual FINGER_CHANNELS from your constants."""
    return FINGER_CHANNELS.copy()


@pytest.fixture
def project_num_channels():
    """Access to actual NUM_CHANNELS from your constants."""
    return NUM_CHANNELS


# =============================================================================
# MediaPipe Landmark Fixtures
# =============================================================================


@pytest.fixture
def sample_landmarks():
    """Sample MediaPipe landmarks for testing (neutral hand position)."""
    landmarks = np.zeros((21, 3))

    # Wrist at origin
    landmarks[0] = [0.5, 0.8, 0.0]

    # Thumb
    landmarks[1] = [0.4, 0.7, 0.0]  # CMC
    landmarks[2] = [0.35, 0.6, 0.0]  # MCP
    landmarks[3] = [0.3, 0.5, 0.0]  # IP
    landmarks[4] = [0.25, 0.4, 0.0]  # TIP

    # Index finger
    landmarks[5] = [0.45, 0.6, 0.0]  # MCP
    landmarks[6] = [0.45, 0.45, 0.0]  # PIP
    landmarks[7] = [0.45, 0.35, 0.0]  # DIP
    landmarks[8] = [0.45, 0.25, 0.0]  # TIP

    # Middle finger
    landmarks[9] = [0.5, 0.55, 0.0]
    landmarks[10] = [0.5, 0.4, 0.0]
    landmarks[11] = [0.5, 0.3, 0.0]
    landmarks[12] = [0.5, 0.2, 0.0]

    # Ring finger
    landmarks[13] = [0.55, 0.6, 0.0]
    landmarks[14] = [0.55, 0.45, 0.0]
    landmarks[15] = [0.55, 0.35, 0.0]
    landmarks[16] = [0.55, 0.25, 0.0]

    # Pinky
    landmarks[17] = [0.6, 0.65, 0.0]
    landmarks[18] = [0.6, 0.55, 0.0]
    landmarks[19] = [0.6, 0.45, 0.0]
    landmarks[20] = [0.6, 0.4, 0.0]

    return landmarks


@pytest.fixture
def open_hand_landmarks():
    """Landmarks for fully open hand (fingers extended)."""
    landmarks = np.zeros((21, 3))

    landmarks[0] = [0.5, 0.8, 0.0]  # Wrist

    # Thumb - extended
    landmarks[1] = [0.35, 0.75, 0.0]
    landmarks[2] = [0.25, 0.70, 0.0]
    landmarks[3] = [0.18, 0.65, 0.0]
    landmarks[4] = [0.10, 0.60, 0.0]

    # Index - extended
    landmarks[5] = [0.45, 0.65, 0.0]
    landmarks[6] = [0.45, 0.50, 0.0]
    landmarks[7] = [0.45, 0.38, 0.0]
    landmarks[8] = [0.45, 0.25, 0.0]

    # Middle - extended
    landmarks[9] = [0.50, 0.63, 0.0]
    landmarks[10] = [0.50, 0.48, 0.0]
    landmarks[11] = [0.50, 0.36, 0.0]
    landmarks[12] = [0.50, 0.23, 0.0]

    # Ring - extended
    landmarks[13] = [0.55, 0.65, 0.0]
    landmarks[14] = [0.55, 0.50, 0.0]
    landmarks[15] = [0.55, 0.38, 0.0]
    landmarks[16] = [0.55, 0.25, 0.0]

    # Pinky - extended
    landmarks[17] = [0.60, 0.68, 0.0]
    landmarks[18] = [0.60, 0.55, 0.0]
    landmarks[19] = [0.60, 0.45, 0.0]
    landmarks[20] = [0.60, 0.35, 0.0]

    return landmarks


@pytest.fixture
def closed_fist_landmarks():
    """Landmarks for closed fist (fingers curled)."""
    landmarks = np.zeros((21, 3))

    landmarks[0] = [0.5, 0.8, 0.0]  # Wrist

    # Thumb - curled
    landmarks[1] = [0.40, 0.75, 0.0]
    landmarks[2] = [0.38, 0.68, 0.0]
    landmarks[3] = [0.42, 0.62, 0.0]
    landmarks[4] = [0.48, 0.58, 0.0]

    # Index - curled
    landmarks[5] = [0.45, 0.68, 0.0]
    landmarks[6] = [0.45, 0.62, 0.0]
    landmarks[7] = [0.42, 0.68, 0.0]
    landmarks[8] = [0.40, 0.72, 0.0]

    # Middle - curled
    landmarks[9] = [0.50, 0.66, 0.0]
    landmarks[10] = [0.50, 0.60, 0.0]
    landmarks[11] = [0.47, 0.66, 0.0]
    landmarks[12] = [0.45, 0.70, 0.0]

    # Ring - curled
    landmarks[13] = [0.55, 0.68, 0.0]
    landmarks[14] = [0.55, 0.62, 0.0]
    landmarks[15] = [0.52, 0.68, 0.0]
    landmarks[16] = [0.50, 0.72, 0.0]

    # Pinky - curled
    landmarks[17] = [0.60, 0.70, 0.0]
    landmarks[18] = [0.60, 0.65, 0.0]
    landmarks[19] = [0.57, 0.70, 0.0]
    landmarks[20] = [0.55, 0.73, 0.0]

    return landmarks


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_servokit():
    """Mock ServoKit for testing without hardware."""
    mock_kit = MagicMock()

    # Create mock servo channels
    servos = {}
    for i in range(16):
        servo = MagicMock()
        servo.angle = None
        servos[i] = servo

    mock_kit.servo = servos
    return mock_kit


@pytest.fixture
def mock_servokit_patch():
    """Patch ServoKit for import-time mocking."""
    with patch("adafruit_servokit.ServoKit") as mock:
        mock_kit = MagicMock()
        servos = {i: MagicMock() for i in range(16)}
        mock_kit.servo = servos
        mock.return_value = mock_kit
        yield mock


# =============================================================================
# Position Fixtures (using project's NUM_CHANNELS)
# =============================================================================


@pytest.fixture
def positions_open():
    """Normalized positions for open hand (all channels at 0)."""
    return {i: 0.0 for i in range(NUM_CHANNELS)}


@pytest.fixture
def positions_closed():
    """Normalized positions for closed hand (all channels at 1)."""
    return {i: 1.0 for i in range(NUM_CHANNELS)}


@pytest.fixture
def positions_half():
    """Normalized positions for half-closed hand."""
    return {i: 0.5 for i in range(NUM_CHANNELS)}


@pytest.fixture
def random_positions():
    """Random normalized positions."""
    np.random.seed(42)  # Reproducible
    return {i: np.random.random() for i in range(NUM_CHANNELS)}
