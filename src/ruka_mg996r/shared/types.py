"""
Type definitions and Pydantic models for RUKA MG996R.
"""

from pydantic import BaseModel, Field

# ====================================================================================
# Calibration Models
# ====================================================================================


class ServoCalibration(BaseModel):
    """
    Calibration data for a single servo.
    """

    channel: int = Field(..., ge=0, lt=16, description="PCA9685 channel number (0-15)")
    joint_name: str = Field(
        ..., description="Name of the joint controlled by this servo"
    )

    # Hardware pulse width limits (calibrated using range_finder.py)
    pulse_min: int = Field(
        ..., ge=400, le=2600, description="Minimum pulse width in microseconds"
    )
    pulse_max: int = Field(
        ..., ge=400, le=2600, description="Maximum pulse width in microseconds"
    )
    # Operational pulse width limits (calibrated using tendon_calibration.py)
    slack_pulse: int | None = Field(
        None, description="Pulse width where the tendon is slack"
    )
    taut_pulse: int | None = Field(
        None, description="Pulse width where the tendon is taut"
    )
    curled_pulse: int | None = Field(
        None, description="Pulse width where the joint is fully curled"
    )
    # Direction flag
    curl_direction_positive: bool = Field(
        True, description="True if higher pulse = more curled"
    )

    @property
    def is_calibrated(self) -> bool:
        """Check if operational positions are calibrated."""
        return all(
            [
                self.slack_pulse is not None,
                self.taut_pulse is not None,
                self.curled_pulse is not None,
            ]
        )

    @property
    def operational_min(self) -> int:
        """Minimum operational pulse width (open, with tendon taut)."""
        assert self.taut_pulse is not None
        return self.taut_pulse

    @property
    def operational_max(self) -> int:
        """Maximum operational pulse width (curled position)."""
        assert self.curled_pulse is not None
        return self.curled_pulse

    @property
    def operational_range(self) -> int:
        """Get the operational pulse range."""
        if not self.is_calibrated:
            return 0
        # Validate invariants
        assert self.taut_pulse is not None and self.curled_pulse is not None
        return abs(self.curled_pulse - self.taut_pulse)

    def normalized_to_pulse(self, normalized: float) -> int:
        """Convert normalized (0=open, 1=curled) to pulse width."""
        normalized = max(0.0, min(1.0, normalized))
        if not self.is_calibrated:
            # Fallback to full range
            if self.curl_direction_positive:
                return int(
                    self.pulse_min + normalized * (self.pulse_max - self.pulse_min)
                )
            else:
                return int(
                    self.pulse_max - normalized * (self.pulse_max - self.pulse_min)
                )
        else:
            if self.curl_direction_positive:
                return int(
                    self.taut_pulse + normalized * (self.curled_pulse - self.taut_pulse)
                )
            else:
                return int(
                    self.taut_pulse - normalized * (self.taut_pulse - self.curled_pulse)
                )

    def pulse_to_normalized(self, pulse: int) -> float:
        """Convert pulse width to normalized position (0=open, 1=curled)."""
        if not self.is_calibrated:
            # Fallback to full range
            if self.curl_direction_positive:
                return (pulse - self.pulse_min) / (self.pulse_max - self.pulse_min)
            else:
                return (self.pulse_max - pulse) / (self.pulse_max - self.pulse_min)
        else:
            if self.curl_direction_positive:
                return (pulse - self.taut_pulse) / (self.curled_pulse - self.taut_pulse)
            else:
                return (self.taut_pulse - pulse) / (self.taut_pulse - self.curled_pulse)


class CalibrationData(BaseModel):
    """
    Calibration data for all servos.
    """

    servos: dict[str, ServoCalibration] = Field(
        default_factory=dict, description="Servo calibrations by channel"
    )
    control_params: dict[str, float] = Field(
        default_factory=lambda: {
            "update_rate_hz": 50.0,
            "smoothing_factor": 0.15,
        },
        description="Control parameters for the motors that drive the robotic hand",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Calibration metadata"
    )

    def get_servo(self, channel: int) -> ServoCalibration | None:
        """Get servo calibration by channel number."""
        return self.servos.get(str(channel))

    def set_servo(self, calibration: ServoCalibration) -> None:
        """Set servo calibration."""
        self.servos[str(calibration.channel)] = calibration


# ===================================================================================
# Runtime State Models
# ===================================================================================


class FingerPositions(BaseModel):
    """
    Current positions of all fingers in normalized form (0=open, 1=curled).
    """

    pinky: float | None = Field(None, ge=0.0, le=1.0)
    ring: float | None = Field(None, ge=0.0, le=1.0)
    middle: float | None = Field(None, ge=0.0, le=1.0)
    index: float | None = Field(None, ge=0.0, le=1.0)
    thumb: float | None = Field(None, ge=0.0, le=1.0)

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary, excluding None values."""
        return {
            finger: pos for finger, pos in self.model_dump(exclude_none=True).items()
        }


class ChannelState(BaseModel):
    """
    Runtime state of a single servo channel.
    """

    channel: int
    joint_name: str
    target_pulse: int
    current_pulse: int
    normalized: float
    velocity: float = 0.0


# ===================================================================================
# Configuration Models
# ===================================================================================
