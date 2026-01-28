"""
Configuration module for RUKLA MG996R server.

Handles loading and saving calibration data
"""

import datetime
import logging
import os
from pathlib import Path

from ruka_mg996r.shared.constants import (
    DEFAULT_CALIBRATION_PATH,
    DEFAULT_PULSE_MAX,
    DEFAULT_PULSE_MIN,
    JOINT_NAMES,
    NUM_CHANNELS,
    THUMB_CHANNELS,
)
from ruka_mg996r.shared.types import CalibrationData, ServoCalibration

logger = logging.getLogger(__name__)


def get_default_calibration() -> CalibrationData:
    """
    Create default if no calibration file exists.
    """
    calibration = CalibrationData()

    for channel in range(NUM_CHANNELS):
        joint_name = JOINT_NAMES.get(channel, f"channel_{channel}")

        curl_direction_positive = channel not in THUMB_CHANNELS

        calibration.servos[str(channel)] = ServoCalibration(
            channel=channel,
            joint_name=joint_name,
            pulse_min=DEFAULT_PULSE_MIN,
            pulse_max=DEFAULT_PULSE_MAX,
            slack_pulse=None,
            taut_pulse=None,
            curled_pulse=None,
            curl_direction_positive=curl_direction_positive,
        )

    return calibration


def load_calibration(filepath: str | None = None) -> CalibrationData:
    """
    Load calibration from JSON file.

    Args:
        filepath (str | None): Path to calibration file. If None, returns filepath from
                               environment variable or default path
                               e.g. (data/calibration/mg996r_calibration.json).

    Returns:
        CalibrationData: Loaded calibration data.

    Raises:
        ValueError: If the file content is invalid.
    """
    # If no filepath provided, return filepath from environment variable or default path
    if filepath is None:
        filepath = os.environ.get("RUKA_CALIBRATION_PATH", DEFAULT_CALIBRATION_PATH)

    path = Path(filepath)

    # If file does not exist or is empty, return default calibration
    if not path.exists() or path.stat().st_size == 0:
        logger.warning(f"Calibration file not found or empty: {filepath}")
        logger.info("Using default calibration.")
        return get_default_calibration()

    with open(path) as f:
        data = f.read()
    # Pydantic validation
    calibration = CalibrationData.model_validate_json(data)

    return calibration


def save_calibration(calibration: CalibrationData, filepath: str | None = None) -> str:
    """
    Save calibration to JSON file.

    Args:
        calibration (CalibrationData): Calibration data to save.
        filepath (str | None): Path to save calibration file. If None, uses
                               environment variable or default path
                               e.g. (data/calibration/mg996r_calibration.json).

    Returns:
        str: Path to saved calibration file.
    """
    # If no filepath provided, return filepath from environment variable or default path
    if filepath is None:
        filepath = os.environ.get("RUKA_CALIBRATION_PATH", DEFAULT_CALIBRATION_PATH)

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Update metadata
    calibration.metadata["last_modified"] = datetime.datetime.now().isoformat()
    calibration.metadata["version"] = "1.0"

    model_json = calibration.model_dump_json(indent=4)

    # write to temp file first then move
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            f.write(model_json)
            f.flush()
            os.fsync(f.fileno())  # force write to disk

        tmp_path.replace(path)
    except OSError as e:
        if tmp_path.exists():
            tmp_path.unlink()
        logger.error(f"Error saving calibration file: {e}")
        raise e

    logger.info(f"Calibration saved to: {filepath}")
    return str(path)
