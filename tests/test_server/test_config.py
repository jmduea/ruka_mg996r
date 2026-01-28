"""
Tests for server/config.py - Configuration and calibration management.

Tests cover:
- Loading calibration from JSON files
- Saving calibration to JSON files
- Default calibration generation
- Error handling for missing/invalid files
"""

import json
import os
from unittest.mock import patch

import pydantic
import pytest

from ruka_mg996r.server.config import (
    get_default_calibration,
    load_calibration,
    save_calibration,
)
from ruka_mg996r.shared.constants import (
    DEFAULT_PULSE_MAX,
    DEFAULT_PULSE_MIN,
    FINGER_CHANNELS,
    NUM_CHANNELS,
    THUMB_CHANNELS,
)
from ruka_mg996r.shared.types import CalibrationData, ServoCalibration


class TestGetDefaultCalibration:
    """Tests for get_default_calibration function."""

    def test_returns_calibration_data(self):
        """Should return a CalibrationData instance."""
        calibration = get_default_calibration()
        assert isinstance(calibration, CalibrationData)

    def test_has_all_channels(self):
        """Should have calibration for all 11 channels."""
        calibration = get_default_calibration()
        assert len(calibration.servos) == NUM_CHANNELS

    def test_channels_have_correct_indices(self):
        """Should have channels 0-10."""
        calibration = get_default_calibration()
        expected_channels = set(str(i) for i in range(NUM_CHANNELS))
        assert set(calibration.servos.keys()) == expected_channels

    def test_thumb_channels_have_reversed_direction(self):
        """Thumb channels should have curl_direction_positive=False."""
        calibration = get_default_calibration()
        for ch in THUMB_CHANNELS:
            servo = calibration.servos[str(ch)]
            assert servo.curl_direction_positive is False, (
                f"Channel {ch} ({servo.joint_name}) should be reversed"
            )

    def test_finger_channels_have_normal_direction(self):
        """Finger channels should have curl_direction_positive=True."""
        calibration = get_default_calibration()
        for ch in FINGER_CHANNELS:
            servo = calibration.servos[str(ch)]
            assert servo.curl_direction_positive is True, (
                f"Channel {ch} ({servo.joint_name}) should be normal"
            )

    def test_servos_have_default_pulse_ranges(self):
        """All servos should have default pulse width ranges."""
        calibration = get_default_calibration()
        for servo in calibration.servos.values():
            assert servo.pulse_min == DEFAULT_PULSE_MIN
            assert servo.pulse_max == DEFAULT_PULSE_MAX

    def test_servos_are_not_calibrated(self):
        """Default servos should not be marked as calibrated."""
        calibration = get_default_calibration()
        for servo in calibration.servos.values():
            assert servo.is_calibrated is False

    def test_has_joint_names(self):
        """All servos should have joint names."""
        calibration = get_default_calibration()
        for servo in calibration.servos.values():
            assert servo.joint_name is not None
            assert len(servo.joint_name) > 0


class TestLoadCalibration:
    """Tests for load_calibration function."""

    def test_loads_valid_calibration_file(self, temp_calibration_file):
        """Should load calibration from a valid JSON file."""
        calibration = load_calibration(str(temp_calibration_file))
        assert isinstance(calibration, CalibrationData)
        assert len(calibration.servos) > 0

    def test_returns_default_for_missing_file(self, tmp_path):
        """Should return default calibration when file doesn't exist."""
        nonexistent_path = tmp_path / "nonexistent.json"
        calibration = load_calibration(str(nonexistent_path))
        assert isinstance(calibration, CalibrationData)
        assert len(calibration.servos) == NUM_CHANNELS

    def test_loads_servo_calibrations(
        self, temp_calibration_file, sample_calibration_data
    ):
        """Should correctly load servo calibration data."""
        calibration = load_calibration(str(temp_calibration_file))

        # Get the first channel from our sample data
        first_ch = sorted(sample_calibration_data["servos"].keys())[0]
        expected = sample_calibration_data["servos"][first_ch]

        servo = calibration.get_servo(int(first_ch))
        assert servo is not None
        assert servo.channel == expected["channel"]
        assert servo.joint_name == expected["joint_name"]
        assert servo.pulse_min == expected["pulse_min"]
        assert servo.pulse_max == expected["pulse_max"]

    def test_loads_operational_positions(
        self, temp_calibration_file, sample_calibration_data
    ):
        """Should load slack, taut, and curled positions."""
        calibration = load_calibration(str(temp_calibration_file))

        # Get the first channel from our sample data
        first_ch = sorted(sample_calibration_data["servos"].keys())[0]
        expected = sample_calibration_data["servos"][first_ch]

        servo = calibration.get_servo(int(first_ch))
        assert servo.slack_pulse == expected["slack_pulse"]
        assert servo.taut_pulse == expected["taut_pulse"]
        assert servo.curled_pulse == expected["curled_pulse"]
        assert servo.is_calibrated is True

    def test_loads_curl_direction(self, temp_calibration_file, sample_calibration_data):
        """Should load curl direction flag."""
        calibration = load_calibration(str(temp_calibration_file))

        # Check curl direction matches expected based on channel type
        for ch_str, expected in sample_calibration_data["servos"].items():
            ch = int(ch_str)
            servo = calibration.get_servo(ch)
            assert (
                servo.curl_direction_positive == expected["curl_direction_positive"]
            ), f"Channel {ch} ({servo.joint_name}) curl direction mismatch"

    def test_loads_control_params(self, temp_calibration_file):
        """Should load control parameters."""
        calibration = load_calibration(str(temp_calibration_file))
        assert calibration.control_params["update_rate_hz"] == 50.0
        assert calibration.control_params["smoothing_factor"] == 0.15

    def test_raises_on_invalid_json(self, tmp_path):
        """Should raise exception for invalid JSON through pydantic validation."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json {{{")

        with pytest.raises(pydantic.ValidationError):
            load_calibration(str(invalid_file))

    def test_uses_environment_variable_path(self, temp_calibration_file):
        """Should use RUKA_CALIBRATION_PATH environment variable."""
        with patch.dict(
            os.environ, {"RUKA_CALIBRATION_PATH": str(temp_calibration_file)}
        ):
            calibration = load_calibration()
            assert len(calibration.servos) > 0

    def test_handles_partial_calibration(self, tmp_path):
        """Should handle files with only some channels calibrated."""
        partial_data = {
            "servos": {
                "0": {
                    "channel": 0,
                    "joint_name": "thumb_cmc",
                    "pulse_min": 700,
                    "pulse_max": 2200,
                }
            }
        }
        partial_file = tmp_path / "partial.json"
        partial_file.write_text(json.dumps(partial_data))

        calibration = load_calibration(str(partial_file))
        assert len(calibration.servos) == 1
        assert "0" in calibration.servos


class TestSaveCalibration:
    """Tests for save_calibration function."""

    def test_saves_calibration_to_file(self, tmp_path):
        """Should save calibration to JSON file."""
        calibration = get_default_calibration()
        filepath = tmp_path / "output.json"

        result_path = save_calibration(calibration, str(filepath))

        assert filepath.exists()
        assert result_path == str(filepath)

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        calibration = get_default_calibration()
        filepath = tmp_path / "nested" / "dir" / "calibration.json"

        save_calibration(calibration, str(filepath))

        assert filepath.exists()

    def test_saved_file_is_valid_json(self, tmp_path):
        """Should save valid JSON that can be loaded."""
        calibration = get_default_calibration()
        filepath = tmp_path / "output.json"

        save_calibration(calibration, str(filepath))

        # Should be loadable
        loaded = load_calibration(str(filepath))
        assert isinstance(loaded, CalibrationData)

    def test_preserves_servo_data(self, tmp_path):
        """Should preserve all servo calibration data."""
        calibration = get_default_calibration()

        # Modify a servo
        servo = calibration.servos["0"]
        servo.pulse_min = 800
        servo.pulse_max = 2100
        servo.slack_pulse = 2000
        servo.taut_pulse = 1900
        servo.curled_pulse = 1100

        filepath = tmp_path / "output.json"
        save_calibration(calibration, str(filepath))

        loaded = load_calibration(str(filepath))
        loaded_servo = loaded.get_servo(0)

        assert loaded_servo.pulse_min == 800
        assert loaded_servo.pulse_max == 2100
        assert loaded_servo.slack_pulse == 2000
        assert loaded_servo.taut_pulse == 1900
        assert loaded_servo.curled_pulse == 1100

    def test_preserves_control_params(self, tmp_path):
        """Should preserve control parameters."""
        calibration = get_default_calibration()
        calibration.control_params["update_rate_hz"] = 60.0
        calibration.control_params["smoothing_factor"] = 0.25

        filepath = tmp_path / "output.json"
        save_calibration(calibration, str(filepath))

        loaded = load_calibration(str(filepath))
        assert loaded.control_params["update_rate_hz"] == 60.0
        assert loaded.control_params["smoothing_factor"] == 0.25

    def test_adds_metadata(self, tmp_path):
        """Should add metadata (version, timestamp)."""
        calibration = get_default_calibration()
        filepath = tmp_path / "output.json"

        save_calibration(calibration, str(filepath))

        loaded = load_calibration(str(filepath))
        assert "version" in loaded.metadata
        assert "last_modified" in loaded.metadata

    def test_uses_environment_variable_path(self, tmp_path):
        """Should use RUKA_CALIBRATION_PATH environment variable."""
        calibration = get_default_calibration()
        filepath = tmp_path / "env_path.json"

        with patch.dict(os.environ, {"RUKA_CALIBRATION_PATH": str(filepath)}):
            save_calibration(calibration)
            assert filepath.exists()

    def test_save_raises_on_error(self, tmp_path):
        """Should raise exception if saving fails."""
        calibration = get_default_calibration()
        # Use an invalid path (e.g., a directory instead of a file)
        invalid_path = tmp_path / "invalid_dir"
        invalid_path.mkdir()

        with pytest.raises(OSError):
            save_calibration(calibration, str(invalid_path))


class TestServoCalibrationMethods:
    """Tests for ServoCalibration model methods."""

    def test_is_calibrated_true(self):
        """Should return True when all operational positions are set."""
        servo = ServoCalibration(
            channel=0,
            joint_name="test",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=2000,
            taut_pulse=1900,
            curled_pulse=1100,
        )
        assert servo.is_calibrated is True

    def test_is_calibrated_false_missing_slack(self):
        """Should return False when slack_pulse is missing."""
        servo = ServoCalibration(
            channel=0,
            joint_name="test",
            pulse_min=700,
            pulse_max=2200,
            taut_pulse=1900,
            curled_pulse=1100,
        )
        assert servo.is_calibrated is False

    def test_is_calibrated_false_missing_taut(self):
        """Should return False when taut_pulse is missing."""
        servo = ServoCalibration(
            channel=0,
            joint_name="test",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=2000,
            curled_pulse=1100,
        )
        assert servo.is_calibrated is False

    def test_is_calibrated_false_missing_curled(self):
        """Should return False when curled_pulse is missing."""
        servo = ServoCalibration(
            channel=0,
            joint_name="test",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=2000,
            taut_pulse=1900,
        )
        assert servo.is_calibrated is False

    def test_operational_range_calibrated(self):
        """Should return operational range for calibrated servo."""
        servo = ServoCalibration(
            channel=0,
            joint_name="test",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=2000,
            taut_pulse=1900,
            curled_pulse=1100,
        )
        assert servo.operational_range == 800  # |1900 - 1100|

    def test_operational_range_uncalibrated(self):
        """Should return 0 for uncalibrated servo."""
        servo = ServoCalibration(
            channel=0,
            joint_name="test",
            pulse_min=700,
            pulse_max=2200,
        )
        assert servo.operational_range == 0

    def test_normalized_to_pulse_positive_direction(self):
        """Should convert normalized position to pulse (positive direction)."""
        servo = ServoCalibration(
            channel=3,  # Finger
            joint_name="index_mcp",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=750,
            taut_pulse=850,
            curled_pulse=1800,
            curl_direction_positive=True,
        )

        # 0.0 = taut (open)
        assert servo.normalized_to_pulse(0.0) == 850

        # 1.0 = curled (closed)
        assert servo.normalized_to_pulse(1.0) == 1800

        # 0.5 = middle
        middle_pulse = 850 + 0.5 * (1800 - 850)
        assert servo.normalized_to_pulse(0.5) == int(middle_pulse)

    def test_normalized_to_pulse_negative_direction(self):
        """Should convert normalized position to pulse (negative direction)."""
        servo = ServoCalibration(
            channel=0,  # Thumb
            joint_name="thumb_cmc",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=2100,
            taut_pulse=2000,
            curled_pulse=1200,
            curl_direction_positive=False,
        )

        # 0.0 = taut (open)
        assert servo.normalized_to_pulse(0.0) == 2000

        # 1.0 = curled (closed)
        assert servo.normalized_to_pulse(1.0) == 1200

        # 0.5 = middle
        middle_pulse = 2000 - 0.5 * (2000 - 1200)
        assert servo.normalized_to_pulse(0.5) == int(middle_pulse)

    def test_normalized_to_pulse_clamps_input(self):
        """Should clamp normalized input to 0-1 range."""
        servo = ServoCalibration(
            channel=3,
            joint_name="index_mcp",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=750,
            taut_pulse=850,
            curled_pulse=1800,
            curl_direction_positive=True,
        )

        # Below 0 should clamp to 0
        assert servo.normalized_to_pulse(-0.5) == 850

        # Above 1 should clamp to 1
        assert servo.normalized_to_pulse(1.5) == 1800

    def test_pulse_to_normalized_positive_direction(self):
        """Should convert pulse to normalized position (positive direction)."""
        servo = ServoCalibration(
            channel=3,
            joint_name="index_mcp",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=750,
            taut_pulse=850,
            curled_pulse=1800,
            curl_direction_positive=True,
        )

        # taut = 0.0
        assert servo.pulse_to_normalized(850) == pytest.approx(0.0)

        # curled = 1.0
        assert servo.pulse_to_normalized(1800) == pytest.approx(1.0)

        # middle
        middle_pulse = 850 + int(0.5 * (1800 - 850))
        assert servo.pulse_to_normalized(middle_pulse) == pytest.approx(0.5, abs=0.01)

    def test_pulse_to_normalized_negative_direction(self):
        """Should convert pulse to normalized position (negative direction)."""
        servo = ServoCalibration(
            channel=0,
            joint_name="thumb_cmc",
            pulse_min=700,
            pulse_max=2200,
            slack_pulse=2100,
            taut_pulse=2000,
            curled_pulse=1200,
            curl_direction_positive=False,
        )

        # taut = 0.0
        assert servo.pulse_to_normalized(2000) == pytest.approx(0.0)

        # curled = 1.0
        assert servo.pulse_to_normalized(1200) == pytest.approx(1.0)
