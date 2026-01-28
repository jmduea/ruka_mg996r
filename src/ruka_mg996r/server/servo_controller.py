import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from ruka_mg996r.shared import JOINT_CHANNELS
from ruka_mg996r.shared.types import CalibrationData, ChannelState, ServoCalibration

logger = logging.getLogger(__name__)


@dataclass
class ServoState:
    """
    Runtime state of a servo motor.

    Attributes:
        channel: PCA9685 channel index (0-15)
        target_pulse: Target pulse width (microseconds)
        current_pulse: Current pulse width (microseconds)
        last_update_time: Timestamp of the last update (seconds since epoch)
        velocity: Current velocity in pulse width units per second
    """

    channel: int
    target_pulse: int
    current_pulse: float
    last_update_time: float = field(default_factory=time.time)

    # "motion-tracking"
    velocity: float = 0.0  # Current velocity in pulse width units per second


class ServoController:
    """
    Controls MG996R servos via PCA9685 with smooth motion interpolation

    Public Attributes:
        calibration: CalibrationData object containing servo calibrations
        simulate: If True, runs in simulation mode without hardware
        update_rate_hz: Frequency of servo updates
        smoothing_factor: Exponential smoothing factor (0.05-0.5)

    Private Attributes:
        _kit: ServoKit instance for PCA9685 control
        _running: Flag indicating if the update thread is running
        _update_thread: Thread for periodic updates
        _lock: Threading lock for state synchronization
        _states: Dictionary mapping channel indices to ServoState objects
        _command_queue: Queue of pending servo commands
        _state_callbacks: List of callback functions for state updates
        _update_count: Count of update cycles for monitoring
        _last_stats_time: Timestamp for latency statistics
        _active_channels: Set of currently active servo channels
    """

    def __init__(
        self,
        calibration: CalibrationData,
        simulate: bool = False,
        update_rate_hz: float = 50.0,
        smoothing_factor: float = 0.15,
    ):
        """
        Initialize servo controller.

        Args:
            calibration: CalibrationData object with servo settings
            simulate: If True, runs in simulation mode without hardware
            update_rate_hz: Frequency of servo updates
            smoothing_factor: Exponential smoothing factor (0.05-0.5)
        """
        # Public attributes
        self.calibration = calibration
        self.simulate = simulate
        self.update_rate_hz = update_rate_hz
        self.smoothing_factor = smoothing_factor

        # Private attributes
        self._kit = None
        self._running = False
        self._update_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # state tracking for each servo
        self._states: dict[int, ServoState] = {}
        # command queue for thead-safe updates
        self._command_queue: deque = deque(maxlen=100)
        # callbacks for state changes
        self._state_callbacks: list[Callable] = []
        # monitoring
        self._update_count = 0
        self._last_stats_time = time.time()

        self._active_channels: set[int] = set()

    # =============================================================================== #
    # Private Methods
    # =============================================================================== #
    # Initialize servo states
    def _init_states(self):
        """Initialize servo states to taut (open) position."""
        for ch_str, servo_cal in self.calibration.servos.items():
            ch = int(ch_str)
            # Start at taut position if calibrated
            if servo_cal.taut_pulse is not None:
                initial_pulse = servo_cal.taut_pulse
            else:
                initial_pulse = (servo_cal.pulse_min + servo_cal.pulse_max) // 2

            self._states[ch] = ServoState(
                channel=ch,
                target_pulse=initial_pulse,
                current_pulse=float(initial_pulse),
                last_update_time=time.time(),
            )
            self._active_channels.add(ch)

    def _update_loop(self):
        """Background loop that updates servo positions at fixed rate."""
        update_interval = 1.0 / self.update_rate_hz

        while self._running:
            loop_start = time.time()
            # Process queue
            self._process_command_queue()
            # Update all positions
            with self._lock:
                self._update_positions()

            self._update_count += 1

            # Performance monitoring
            if time.time() - self._last_stats_time > 5.0:
                actual_rate = self._update_count / (time.time() - self._last_stats_time)
                logger.debug(f"Servo loop: {actual_rate:.1f}Hz")
                self._update_count = 0
                self._last_stats_time = time.time()

            # Sleep to maintain update rate
            elapsed = time.time() - loop_start
            sleep_time = update_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _process_command_queue(self) -> None:
        """Process pending commands from the queue."""
        while self._command_queue:
            try:
                cmd = self._command_queue.popleft()
                self._apply_command(cmd)
            except IndexError:
                break

    def _apply_command(self, cmd: dict) -> None:
        """Apply a single command to update servo target positions."""
        cmd_type = cmd.get("type")

        match cmd_type:
            case "set_normalized":
                # Set finger positions using normalized values (0-1)
                positions = cmd.get("positions", {})
                for ch_str, normalized in positions.items():
                    ch = int(ch_str)
                    servo_cal = self.calibration.get_servo(ch)
                    if servo_cal:
                        target_pulse = servo_cal.normalized_to_pulse(normalized)
                        with self._lock:
                            self._states[ch].target_pulse = target_pulse

            case "set_pulse":
                # Set raw pulse widths
                pulses = cmd.get("pulses", {})
                for ch_str, pulse in pulses.items():
                    ch = int(ch_str)
                    with self._lock:
                        if ch in self._states:
                            self._states[ch].target_pulse = int(pulse)

            case "release":
                channels = cmd.get("channels", list(self._active_channels))
                self._release_channels(channels)

            case _:
                print("Unknown command type received")

    def _update_positions(self) -> None:
        """
        Update all servo positions using exponential smoothing.
        Called from the update loop
        """
        current_time = time.time()

        for ch, state in self._states.items():
            servo_cal = self.calibration.get_servo(ch)
            if not servo_cal:
                continue

            dt = current_time - state.last_update_time
            state.last_update_time = current_time

            # determine how far off target we are
            error = state.target_pulse - state.current_pulse

            # skip if already there
            if abs(error) < 1.0:
                state.current_pulse = float(state.target_pulse)
                state.velocity = 0.0
                continue

            # Exponential smoothing
            # Controlled by smoothing_factor
            alpha = self.smoothing_factor

            desired_velocity = error * alpha * self.update_rate_hz

            # Safety limits
            max_velocity = (
                300.0  # TODO: move to servo calibration
                * (servo_cal.pulse_max - servo_cal.pulse_min)
                / 180.0
            )
            desired_velocity = np.clip(desired_velocity, -max_velocity, max_velocity)

            # Update pos
            state.current_pulse += desired_velocity * dt
            state.velocity = desired_velocity

            # Clamp to limits
            if servo_cal.is_calibrated:
                op_min = min(servo_cal.taut_pulse, servo_cal.curled_pulse)  # type: ignore
                op_max = max(servo_cal.taut_pulse, servo_cal.curled_pulse)  # type: ignore
            else:
                op_min = servo_cal.pulse_min
                op_max = servo_cal.pulse_max

            state.current_pulse = np.clip(state.current_pulse, op_min, op_max)

            # Send to hardware
            self._write_servo(ch, int(state.current_pulse), servo_cal)

    def _write_servo(
        self, channel: int, pulse: int, servo_cal: ServoCalibration
    ) -> None:
        """
        Write pulse width to servo channel.

        This is what actually sends the command to the PCA9685 hardware to move the
        servo to the converted angle.
        """
        if self.simulate:
            return  # No hardware in simulation mode

        if self._kit is None:
            logger.warning("No PCA9685 kit initialized")
            return

        try:
            # Convert pulse to angle (0-180) for ServoKit
            # TODO: Verify/Unit test this conversion
            pulse_range = servo_cal.pulse_max - servo_cal.pulse_min
            angle = (pulse - servo_cal.pulse_min) / pulse_range * 180.0
            angle = np.clip(angle, 0, 180)
            self._kit.servo[channel].angle = angle
        except Exception as e:
            logger.error(f"Error writing to servo channel {channel}: {e}")

    def _release_channels(self, channels: list[int]):
        """Release specified servo channels."""
        if self.simulate:
            return

        if self._kit is None:
            return

        for ch in channels:
            try:
                self._kit.servo[ch].angle = None  # Disable PWM signal
            except Exception as e:
                logger.error(f"Error releasing servo channel {ch}: {e}")

    # ============================================================================== #
    # PUBLIC API
    # ============================================================================== #

    def start(self) -> None:
        """Start the background update loop."""
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        logger.info(f"Servo update loop started at {self.update_rate_hz}Hz")

    def stop(self) -> None:
        """Stop the background update loop and release servos."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)

        self.release_all()
        logger.info("Servo Controller stopped")

    def connect(self) -> bool:
        """
        Initialize conmnection to PCA9685.

        Returns:
            True if connection successful, False otherwise.

        """
        if self.simulate:
            logger.info("Running in simulation mode (no hardware)")
            self._init_states()
            return True

        try:
            from adafruit_servokit import ServoKit

            self._kit = ServoKit(channels=16)
            # Configure each channel
            for ch_str, servo_cal in self.calibration.servos.items():
                ch = int(ch_str)
                self._kit.servo[ch].set_pulse_width_range(
                    servo_cal.pulse_min, servo_cal.pulse_max
                )
                self._active_channels.add(ch)

            self._init_states()
            logger.info(
                f"Connected to PCA9685, configured {len(self._active_channels)} channels."
            )
            return True

        except ImportError as e:
            logger.error(f"Failed to import ServoKit: {e}")
            logger.error("Ensure adafruit-circuitpython-servokit is installed.")
            logger.error(
                "Run `uv sync --extra server` to install missing dependencies."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to connect to PCA9685: {e}")
            return False

    def set_finger_positions(self, positions: dict[str, float]) -> None:
        """
        Set finger positions using finger names.

        Args:
            positions: Dict mapping finger name to normalized posoition (0.0-1.0)
                       e.g., {'index': 0.5, 'thumb': 0.3}
        TODO: We should map to joint names instead of finger names or handle lists of normalized positions (2 for fingers, 3 for thumb)
        TODO: update documentation, handling
        """
        channel_positions = {}

        for finger_name, normalized in positions.items():
            logger.debug(
                f"Setting finger '{finger_name}' to normalized position {normalized}"
            )
            channels = JOINT_CHANNELS.get(finger_name, [])
            logger.debug(f"Mapped to channels: {channels}")
            for ch in channels:
                logger.debug(
                    f"Setting channel {ch} to normalized position {normalized}"
                )
                channel_positions[str(ch)] = normalized

        self._command_queue.append(
            {"type": "set_normalized", "positions": channel_positions}
        )
        logger.debug(f"Queued finger position command: {channel_positions}")

    def set_channel_positions(self, positions: dict[int, float]) -> None:
        """
        Set individual channel positions.

        Args:
            positions: Dict mapping channel to normalized position (0.0-1.0)
        """
        self._command_queue.append(
            {
                "type": "set_normalized",
                "positions": {str(ch): pos for ch, pos in positions.items()},
            }
        )

    def set_raw_pulses(self, pulses: dict[int, int]) -> None:
        """
        Set raw pulse widths (for calibration/testing).

        Args:
            pulses: Dict mapping channel to pulse width in microseconds
        """
        self._command_queue.append(
            {
                "type": "set_pulse",
                "pulses": {str(ch): pulse for ch, pulse in pulses.items()},
            }
        )

    def release_all(self) -> None:
        """Release all servos."""
        self._command_queue.append(
            {"type": "release", "channels": list(self._active_channels)}
        )

    def release_channel(self, channel: int) -> None:
        """Release a specific channel."""
        self._command_queue.append({"type": "release", "channels": [channel]})

    def get_state(self) -> dict[int, ChannelState]:
        """Get current state of all servos."""
        with self._lock:
            result = {}
            for ch, state in self._states.items():
                servo_cal = self.calibration.get_servo(ch)
                if servo_cal:
                    result[ch] = ChannelState(
                        channel=ch,
                        joint_name=servo_cal.joint_name,
                        target_pulse=state.target_pulse,
                        current_pulse=int(state.current_pulse),
                        normalized=servo_cal.pulse_to_normalized(
                            int(state.current_pulse)
                        ),
                        velocity=state.velocity,
                    )
            return result

    def set_smoothing(self, factor: float) -> None:
        """Adjust smoothing factor (0.05-0.5, lower=smoother)."""
        self.smoothing_factor = np.clip(factor, 0.05, 0.5)

    @property
    def is_running(self) -> bool:
        """Check if the controller is running."""
        return self._running

    @property
    def active_channels(self) -> set[int]:
        """Get the set of active servo channels."""
        return self._active_channels.copy()
