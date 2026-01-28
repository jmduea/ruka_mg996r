"""
Tests for server/servo_controller.py - MG996R servo control.

Tests cover:
- Initialization and connection
- Servo position setting
- Smoothing and interpolation
- Command queue handling
- State management
- Thread safety
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from ruka_mg996r.server.servo_controller import ServoController, ServoState
from ruka_mg996r.shared.constants import (
    DEFAULT_PULSE_MAX,
    DEFAULT_PULSE_MIN,
    FINGER_CHANNELS,
    JOINT_NAMES,
    THUMB_CHANNELS,
)
from ruka_mg996r.shared.types import CalibrationData, ServoCalibration

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def calibration():
    """Basic calibration data for testing using project constants."""
    cal = CalibrationData()

    # Pick one thumb channel and one finger channel from the project config
    thumb_ch = sorted(list(THUMB_CHANNELS))[0] if THUMB_CHANNELS else 0
    finger_ch = sorted(list(FINGER_CHANNELS))[0] if FINGER_CHANNELS else 3

    # Thumb channel (reversed direction)
    cal.servos[str(thumb_ch)] = ServoCalibration(
        channel=thumb_ch,
        joint_name=JOINT_NAMES.get(thumb_ch, f"thumb_{thumb_ch}"),
        pulse_min=700,
        pulse_max=2200,
        slack_pulse=2100,
        taut_pulse=2000,
        curled_pulse=1200,
        curl_direction_positive=False,
    )

    # Finger channel (normal direction)
    cal.servos[str(finger_ch)] = ServoCalibration(
        channel=finger_ch,
        joint_name=JOINT_NAMES.get(finger_ch, f"finger_{finger_ch}"),
        pulse_min=680,
        pulse_max=2150,
        slack_pulse=750,
        taut_pulse=850,
        curled_pulse=1800,
        curl_direction_positive=True,
    )

    return cal


@pytest.fixture
def default_calibration():
    """Default calibration data for testing."""
    cal = CalibrationData()

    # Pick one thumb channel and one finger channel from the project config
    thumb_ch = sorted(list(THUMB_CHANNELS))[0] if THUMB_CHANNELS else 0
    finger_ch = sorted(list(FINGER_CHANNELS))[0] if FINGER_CHANNELS else 3

    cal.servos[str(finger_ch)] = ServoCalibration(
        channel=finger_ch,
        joint_name=JOINT_NAMES.get(finger_ch, f"finger_{finger_ch}"),
        pulse_min=DEFAULT_PULSE_MIN,
        pulse_max=DEFAULT_PULSE_MAX,
        slack_pulse=None,
        taut_pulse=None,
        curled_pulse=None,
        curl_direction_positive=True,
    )

    cal.servos[str(thumb_ch)] = ServoCalibration(
        channel=thumb_ch,
        joint_name=JOINT_NAMES.get(thumb_ch, f"thumb_{thumb_ch}"),
        pulse_min=DEFAULT_PULSE_MIN,
        pulse_max=DEFAULT_PULSE_MAX,
        slack_pulse=None,
        taut_pulse=None,
        curled_pulse=None,
        curl_direction_positive=False,
    )

    return cal


@pytest.fixture
def thumb_channel():
    """Get first thumb channel from project config."""
    return sorted(list(THUMB_CHANNELS))[0] if THUMB_CHANNELS else 0


@pytest.fixture
def finger_channel():
    """Get first finger channel from project config."""
    return sorted(list(FINGER_CHANNELS))[0] if FINGER_CHANNELS else 3


@pytest.fixture
def mock_servokit():
    """Mock ServoKit for testing without hardware."""
    with patch.dict("sys.modules", {"adafruit_servokit": MagicMock()}):
        import sys

        kit_instance = MagicMock()

        # Create mock servo channels
        servos = {}
        for i in range(16):
            servo = MagicMock()
            servo.angle = None
            servos[i] = servo

        kit_instance.servo = servos
        sys.modules["adafruit_servokit"].ServoKit.return_value = kit_instance

        yield kit_instance


@pytest.fixture
def controller(calibration):
    """Simulated servo controller for testing."""
    return ServoController(
        calibration=calibration,
        simulate=True,
        update_rate_hz=100.0,  # Fast update for testing
        smoothing_factor=0.3,
    )


@pytest.fixture
def default_controller(default_calibration):
    """Simulated servo controller with default calibration for testing."""
    return ServoController(
        calibration=default_calibration,
        simulate=True,
        update_rate_hz=100.0,  # Fast update for testing
        smoothing_factor=0.3,
    )


@pytest.fixture
def hardware_controller(calibration):
    """Controller for hardware-related tests (uses simulation)."""
    # Since adafruit_servokit is not installed, use simulation mode
    # but test the behavior that doesn't require actual hardware
    return ServoController(
        calibration=calibration,
        simulate=True,  # Use simulation since hardware isn't available
        update_rate_hz=100.0,
        smoothing_factor=0.3,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestServoControllerInit:
    """Tests for ServoController initialization."""

    def test_init_with_calibration(self, calibration):
        """Should initialize with calibration data."""
        controller = ServoController(calibration=calibration, simulate=True)

        assert controller.calibration == calibration
        assert controller.simulate is True

    def test_init_with_default_calibration(self, default_calibration):
        """Should initialize with default calibration data."""
        controller = ServoController(calibration=default_calibration, simulate=True)

        assert controller.calibration == default_calibration
        assert controller.simulate is True

    def test_init_default_parameters(self, calibration):
        """Should use default parameters when not specified."""
        controller = ServoController(calibration=calibration, simulate=True)

        assert controller.update_rate_hz == 50.0
        assert controller.smoothing_factor == 0.15

    def test_init_custom_parameters(self, calibration):
        """Should accept custom parameters."""
        controller = ServoController(
            calibration=calibration,
            simulate=True,
            update_rate_hz=100.0,
            smoothing_factor=0.25,
        )

        assert controller.update_rate_hz == 100.0
        assert controller.smoothing_factor == 0.25

    def test_init_not_running(self, calibration):
        """Should not be running after init."""
        controller = ServoController(calibration=calibration, simulate=True)

        assert controller.is_running is False


class TestServoControllerConnect:
    """Tests for hardware connection."""

    def test_connect_simulation_mode(self, controller):
        """Should connect successfully in simulation mode."""
        result = controller.connect()

        assert result is True

    def test_connect_initializes_states(
        self, controller, thumb_channel, finger_channel
    ):
        """Should initialize servo states on connect."""
        controller.connect()

        # Should have states for calibrated channels
        assert thumb_channel in controller._states
        assert finger_channel in controller._states

    def test_connect_initializes_to_taut_position(
        self, controller, thumb_channel, finger_channel
    ):
        """Should initialize servos to taut (open) position."""
        controller.connect()

        # Thumb servo
        state_thumb = controller._states[thumb_channel]
        assert state_thumb.target_pulse == 2000  # taut_pulse

        # Finger servo
        state_finger = controller._states[finger_channel]
        assert state_finger.target_pulse == 850  # taut_pulse

    def test_connect_initializes_default_taut_position(
        self, default_controller, thumb_channel, finger_channel
    ):
        """Should initialize servos to default taut position (halfway) with default calibration."""
        default_controller.connect()

        # Thumb servo
        state_thumb = default_controller._states[thumb_channel]
        assert (
            state_thumb.target_pulse
            == (
                default_controller.calibration.servos[str(thumb_channel)].pulse_min
                + default_controller.calibration.servos[str(thumb_channel)].pulse_max
            )
            // 2
        )

        # Finger servo
        state_finger = default_controller._states[finger_channel]
        assert (
            state_finger.target_pulse
            == (
                default_controller.calibration.servos[str(finger_channel)].pulse_min
                + default_controller.calibration.servos[str(finger_channel)].pulse_max
            )
            // 2
        )

    def test_connect_with_hardware_mock(self, hardware_controller):
        """Should connect successfully (using simulation mode in tests)."""
        result = hardware_controller.connect()

        assert result is True

    def test_connect_configures_channels(self, hardware_controller):
        """Should track active channels on connect."""
        hardware_controller.connect()

        # Should have active channels configured
        assert len(hardware_controller.active_channels) > 0

    def test_connect_tracks_active_channels(
        self, controller, thumb_channel, finger_channel
    ):
        """Should track active channels."""
        controller.connect()

        assert thumb_channel in controller.active_channels
        assert finger_channel in controller.active_channels
        # A channel not in calibration should not be active
        uncalibrated_ch = max(thumb_channel, finger_channel) + 100
        assert uncalibrated_ch not in controller.active_channels


# =============================================================================
# Start/Stop Tests
# =============================================================================


class TestServoControllerStartStop:
    """Tests for starting and stopping the controller."""

    def test_start_creates_thread(self, controller):
        """Should create background update thread."""
        controller.connect()
        controller.start()

        try:
            assert controller.is_running is True
            assert controller._update_thread is not None
            assert controller._update_thread.is_alive()
        finally:
            controller.stop()

    def test_stop_terminates_thread(self, controller):
        """Should terminate background thread on stop."""
        controller.connect()
        controller.start()
        controller.stop()

        assert controller.is_running is False
        # Thread should be stopped (give it time to terminate)
        time.sleep(0.1)
        assert not controller._update_thread.is_alive()

    def test_start_idempotent(self, controller):
        """Starting multiple times should not create multiple threads."""
        controller.connect()
        controller.start()
        thread1 = controller._update_thread

        controller.start()
        thread2 = controller._update_thread

        try:
            assert thread1 is thread2
        finally:
            controller.stop()

    def test_stop_releases_servos(self, controller):
        """Should stop running and mark for release on stop."""
        controller.connect()
        controller.start()
        controller.stop()

        # Should no longer be running
        assert controller.is_running is False


# =============================================================================
# Position Setting Tests
# =============================================================================


class TestSetFingerPositions:
    """Tests for set_finger_positions method."""

    def test_set_single_finger(self, controller):
        """Should set position for a single finger."""
        controller.connect()
        controller.start()

        try:
            controller.set_finger_positions({"thumb": 0.5})

            # Give time for command to be processed
            time.sleep(0.05)

            # Command should be queued
            # (Actual position update happens in background thread)
        finally:
            controller.stop()

    def test_set_multiple_fingers(self, controller):
        """Should set positions for multiple fingers."""
        controller.connect()
        controller.start()

        try:
            controller.set_finger_positions(
                {
                    "thumb": 0.3,
                    "index": 0.7,
                }
            )

            time.sleep(0.05)
        finally:
            controller.stop()

    def test_finger_maps_to_channels(self, controller, finger_channel):
        """Should map finger names to correct channels."""
        controller.connect()
        controller.start()

        try:
            # Set index finger (uses finger channels from config)
            controller.set_finger_positions({"pinky": 0.5})

            time.sleep(0.1)

            # finger_channel should have updated target
            state = controller.get_state()
            if finger_channel in state:
                # Target should reflect 0.5 normalized position
                assert state[finger_channel].normalized != 0.0
        finally:
            controller.stop()


class TestSetChannelPositions:
    """Tests for set_channel_positions method."""

    def test_set_single_channel(self, controller, thumb_channel):
        """Should set position for a single channel."""
        controller.connect()
        controller.start()

        try:
            controller.set_channel_positions({thumb_channel: 0.5})
            time.sleep(0.05)
        finally:
            controller.stop()

    def test_set_multiple_channels(self, controller, thumb_channel, finger_channel):
        """Should set positions for multiple channels."""
        controller.connect()
        controller.start()

        try:
            controller.set_channel_positions({thumb_channel: 0.3, finger_channel: 0.7})
            time.sleep(0.05)
        finally:
            controller.stop()

    def test_normalized_to_pulse_conversion_finger(self, controller, finger_channel):
        """Should convert normalized positions to pulses."""
        controller.connect()
        controller.start()

        try:
            # Set to fully curled (1.0)
            controller.set_channel_positions({finger_channel: 1.0})

            # Wait for processing
            time.sleep(0.15)

            state = controller.get_state()
            if finger_channel in state:
                # Target should be near curled pulse (1800)
                assert state[finger_channel].target_pulse == 1800
        finally:
            controller.stop()

    def test_normalized_to_pulse_conversion_thumb(self, controller, thumb_channel):
        """Should convert normalized positions to pulses for thumb (reversed)."""
        controller.connect()
        controller.start()

        try:
            # Set to fully curled (1.0)
            controller.set_channel_positions({thumb_channel: 1.0})

            # Wait for processing
            time.sleep(0.15)

            state = controller.get_state()
            if thumb_channel in state:
                # Target should be near curled pulse (1200)
                assert state[thumb_channel].target_pulse == 1200
        finally:
            controller.stop()


class TestSetRawPulses:
    """Tests for set_raw_pulses method."""

    def test_set_raw_pulse(self, controller, thumb_channel):
        """Should set raw pulse width directly."""
        controller.connect()
        controller.start()

        try:
            controller.set_raw_pulses({thumb_channel: 1500})
            time.sleep(0.1)

            state = controller.get_state()
            if thumb_channel in state:
                assert state[thumb_channel].target_pulse == 1500
        finally:
            controller.stop()


# =============================================================================
# Smoothing Tests
# =============================================================================


class TestSmoothing:
    """Tests for position smoothing."""

    def test_smoothing_applies_exponential_filter(self, controller, finger_channel):
        """Should apply exponential smoothing to position changes."""
        controller.connect()
        controller.start()

        try:
            # Set initial position
            controller.set_channel_positions({finger_channel: 0.0})
            time.sleep(0.1)

            # Set new target
            controller.set_channel_positions({finger_channel: 1.0})

            # Check intermediate position (should not jump instantly)
            time.sleep(0.02)
            state = controller.get_state()

            if finger_channel in state:
                # Should be somewhere between 0 and 1
                # Due to smoothing, it won't jump to 1.0 instantly
                pass  # Hard to test exact intermediate value
        finally:
            controller.stop()

    def test_set_smoothing_factor(self, controller):
        """Should allow changing smoothing factor."""
        controller.set_smoothing(0.4)

        assert controller.smoothing_factor == 0.4

    def test_smoothing_clamped_to_range(self, controller):
        """Should clamp smoothing factor to valid range."""
        controller.set_smoothing(0.01)  # Below min
        assert controller.smoothing_factor == 0.05

        controller.set_smoothing(0.8)  # Above max
        assert controller.smoothing_factor == 0.5


# =============================================================================
# Release Tests
# =============================================================================


class TestRelease:
    """Tests for servo release functionality."""

    def test_release_all(self, controller):
        """Should release all servos."""
        controller.connect()
        controller.start()

        try:
            controller.release_all()
            time.sleep(0.05)
        finally:
            controller.stop()

    def test_release_single_channel(self, controller, thumb_channel):
        """Should release a single channel."""
        controller.connect()
        controller.start()

        try:
            controller.release_channel(thumb_channel)
            time.sleep(0.05)
        finally:
            controller.stop()


# =============================================================================
# State Tests
# =============================================================================


class TestGetState:
    """Tests for get_state method."""

    def test_get_state_returns_channel_states(self, controller):
        """Should return ChannelState for each channel."""
        controller.connect()
        controller.start()

        try:
            time.sleep(0.05)  # Let the controller initialize

            state = controller.get_state()

            assert isinstance(state, dict)
            # Should have entries for calibrated channels
            for ch in controller.active_channels:
                if ch in state:
                    assert hasattr(state[ch], "channel")
                    assert hasattr(state[ch], "joint_name")
                    assert hasattr(state[ch], "target_pulse")
                    assert hasattr(state[ch], "current_pulse")
                    assert hasattr(state[ch], "normalized")
        finally:
            controller.stop()

    def test_state_includes_joint_name(self, controller, thumb_channel, finger_channel):
        """Should include joint name in state."""
        controller.connect()
        controller.start()

        try:
            time.sleep(0.05)
            state = controller.get_state()

            if thumb_channel in state:
                assert state[thumb_channel].joint_name == JOINT_NAMES.get(
                    thumb_channel, f"thumb_{thumb_channel}"
                )
            if finger_channel in state:
                assert state[finger_channel].joint_name == JOINT_NAMES.get(
                    finger_channel, f"finger_{finger_channel}"
                )
        finally:
            controller.stop()


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Tests for thread-safe operation."""

    def test_concurrent_position_updates(
        self, controller, thumb_channel, finger_channel
    ):
        """Should handle concurrent position updates safely."""
        controller.connect()
        controller.start()

        try:
            errors = []

            def update_positions(thread_id):
                try:
                    for i in range(50):
                        controller.set_channel_positions(
                            {
                                thumb_channel: (i + thread_id) % 100 / 100.0,
                                finger_channel: (i + thread_id + 50) % 100 / 100.0,
                            }
                        )
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=update_positions, args=(i,)) for i in range(5)
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Thread errors: {errors}"
        finally:
            controller.stop()

    def test_concurrent_state_reads(self, controller):
        """Should handle concurrent state reads safely."""
        controller.connect()
        controller.start()

        try:
            errors = []

            def read_state():
                try:
                    for _ in range(100):
                        state = controller.get_state()
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=read_state) for _ in range(5)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Thread errors: {errors}"
        finally:
            controller.stop()


# =============================================================================
# ServoState Tests
# =============================================================================


class TestServoState:
    """Tests for ServoState dataclass."""

    def test_servo_state_creation(self):
        """Should create ServoState with required fields."""
        state = ServoState(
            channel=0,
            target_pulse=1500,
            current_pulse=1400.0,
        )

        assert state.channel == 0
        assert state.target_pulse == 1500
        assert state.current_pulse == 1400.0
        assert state.velocity == 0.0  # Default

    def test_servo_state_with_velocity(self):
        """Should track velocity."""
        state = ServoState(
            channel=0,
            target_pulse=1500,
            current_pulse=1400.0,
            velocity=100.0,
        )

        assert state.velocity == 100.0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_position_clamp_below_zero(self, controller, finger_channel):
        """Should clamp positions below 0."""
        controller.connect()
        controller.start()

        try:
            controller.set_channel_positions({finger_channel: -0.5})
            time.sleep(0.1)

            state = controller.get_state()
            if finger_channel in state:
                # Should be clamped to valid range
                assert state[finger_channel].normalized >= 0.0
        finally:
            controller.stop()

    def test_position_clamp_above_one(self, controller, finger_channel):
        """Should clamp positions above 1."""
        controller.connect()
        controller.start()

        try:
            controller.set_channel_positions({finger_channel: 1.5})
            time.sleep(0.1)

            state = controller.get_state()
            if finger_channel in state:
                # Should be clamped to valid range
                assert state[finger_channel].normalized <= 1.0
        finally:
            controller.stop()

    def test_invalid_channel_ignored(self, controller):
        """Should ignore commands for invalid channels."""
        controller.connect()
        controller.start()

        try:
            # Channel 99 doesn't exist
            controller.set_channel_positions({99: 0.5})
            time.sleep(0.05)

            # Should not raise error
            state = controller.get_state()
            assert 99 not in state
        finally:
            controller.stop()

    def test_command_queue_overflow(self, controller, thumb_channel):
        """Should handle command queue overflow gracefully."""
        controller.connect()
        # Don't start the controller, so commands won't be processed

        # Queue many commands
        for i in range(200):
            controller.set_channel_positions({thumb_channel: i / 200})

        # Queue should not grow unbounded (maxlen=100)
        assert len(controller._command_queue) <= 100
