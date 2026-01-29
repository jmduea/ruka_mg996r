"""
Tendon Calibration for RUKA Hand.
"""

import time

from ruka_mg996r.server.config import load_calibration, save_calibration
from ruka_mg996r.shared.constants import NUM_CHANNELS, THUMB_CHANNELS
from ruka_mg996r.shared.types import CalibrationData
from ruka_mg996r.shared.utils import clear_screen, getch

# Settling time after moving servo
SETTLING_TIME = 0.4

# Approach overshoot for backlash compensation
APPROACH_OVERSHOOT = 50  # microseconds


class TendonCalibrator:
    """
    Interactive tendon calibration tool.

    Calibrates three positions per joint:
    - Slack: Tendon loos, finger relaxed
    - Taut: Tendon just taut, no finger movement yet
    - Curled: Finger fully curled
    """

    def __init__(self, calibration: CalibrationData, output_path: str):
        self.calibration: CalibrationData = calibration
        self.output_path: str = output_path
        self._kit = None
        self._current_channel: int = 0
        self._current_pulse: int | None = None
        self._unsaved_changes: bool = False

    def connect(self) -> bool:
        """Connect to the PCA9685 servo controller."""
        try:
            from adafruit_servokit import ServoKit

            self._kit = ServoKit(channels=16)
            # Set pulse width ranges for each servo based on calibration data
            for ch_str, servo in self.calibration.servos.items():
                ch = int(ch_str)
                self._kit.servo[ch].set_pulse_width_range(
                    servo.pulse_min, servo.pulse_max
                )

            print("Connected to PCA9685.")
            return True
        except Exception as e:
            print(f"Failed to connect to PCA9685: {e}")
            return False

    def _set_pulse(self, channel: int, pulse: int):
        """Set servo to specific pulse width."""
        servo = self.calibration.servos.get(str(channel))
        if not servo:
            return

        # clamp pulse within min/max
        pulse = max(servo.pulse_min, min(servo.pulse_max, pulse))
        pulse_range = servo.pulse_max - servo.pulse_min
        angle = (pulse - servo.pulse_min) / pulse_range * 180.0
        angle = max(0.0, min(180.0, angle))

        try:
            self._kit.servo[channel].angle = angle
            self._current_pulse = pulse
            time.sleep(SETTLING_TIME)
        except Exception as e:
            print(f"Failed to set pulse on channel {channel}: {e}")

    def _approach_from_below(self, channel: int, target_pulse: int):
        """
        Approach target from below to eliminate backlash.

        Always approach calibration positions from the same direction for consistent results.
        """
        servo = self.calibration.servos.get(str(channel))
        if not servo:
            return

        # Move to a position below the target
        below_pulse = max(servo.pulse_min, target_pulse - APPROACH_OVERSHOOT)
        self._set_pulse(channel, below_pulse)
        time.sleep(0.2)

        # Approach target
        self._set_pulse(channel, target_pulse)

    def _release(self, channel: int):
        """Release servo"""
        try:
            self._kit.servo[channel].angle = None
        except Exception as e:
            print(f"Failed to release servo on channel {channel}: {e}")

    def _release_all(self):
        """Release all servos"""
        for ch in range(16):
            try:
                self._release(ch)
            except Exception as e:
                print(f"Failed to release servo on channel {ch}: {e}")

    def _print_header(self):
        """Print calibration interface header."""
        clear_screen()

        ch = self._current_channel
        servo = self.calibration.servos.get(str(ch))

        print(f"{'=' * 60}")
        print("  RUKA MG996R Tendon Calibrator")
        print(f"{'=' * 60}\n")

        if servo:
            joint_name = servo.joint_name
            is_thumb = ch in THUMB_CHANNELS
            direction = "THUMB (reversed)" if is_thumb else "FINGER (normal)"

            print(f"  Channel: {ch} - {joint_name}")
            print(f"  Type: {direction}")
            print(f"  Pulse Range: {servo.pulse_max} - {servo.pulse_min} µs\n")

            # Current pulse display
            print(f"  ┌{'─' * 42}┐")
            print(f"  |  Current Pulse: {self._current_pulse:>6} µs           |")
            print(f"  └{'─' * 42}┘\n")

            # Visual bar
            bar_width = 30
            range_size = servo.pulse_max - servo.pulse_min
            if range_size > 0:
                pos = int(
                    (self._current_pulse - servo.pulse_min) / range_size * bar_width
                )
                pos = max(0, min(bar_width - 1, pos))
            else:
                pos = 0
            bar = "-" * pos + "█" + "-" * (bar_width - pos - 1)
            print(f"  │  {servo.pulse_min}µs [{bar}] {servo.pulse_max}µs │")
            print("  │                                          │")

            # Calibration values
            slack = f"{servo.slack_pulse}µs" if servo.slack_pulse else "not set"
            taut = f"{servo.taut_pulse}µs" if servo.taut_pulse else "not set"
            curled = f"{servo.curled_pulse}µs" if servo.curled_pulse else "not set"

            print(f"  │  SLACK:  {slack:>12}                   │")
            print(f"  │  TAUT:   {taut:>12}                   │")
            print(f"  │  CURLED: {curled:>12}                   │")
            print("  │                                          │")

            status = "✓ CALIBRATED" if servo.is_calibrated else "○ incomplete"
            print(f"  │  Status: {status:>20}          │")
            print(f"  └{'─' * 42}┘")
            print()

        # Controls
        print("  Controls:")
        print("    [a]/[d]  -50µs/+50µs    [j]/[l]  -10µs/+10µs")
        print("    [1] Set SLACK           [2] Set TAUT")
        print("    [3] Set CURLED          [t] Test range")
        print("    [m] Move to middle      [r] Release servo")
        print("    [n]/[p] Next/Prev       [s] Save")
        print("    [w] Warm-up cycle       [q] Quit\n")

    def _print_summary(self):
        """Print summary of all channels."""
        print("  All Joints:")
        print("  " + "-" * 56)
        print(
            f"  {'Ch':<4} {'Joint':<14} {'Slack':>8} {'Taut':>8} {'Curled':>8} {'Status':<10}"
        )
        print("  " + "-" * 56)

        for ch in range(NUM_CHANNELS):
            servo = self.calibration.servos.get(str(ch))
            if not servo:
                continue

            marker = "→ " if ch == self._current_channel else "  "
            status = "✓" if servo.is_calibrated else "○"

            slack = str(servo.slack_pulse) if servo.slack_pulse else "?"
            taut = str(servo.taut_pulse) if servo.taut_pulse else "?"
            curled = str(servo.curled_pulse) if servo.curled_pulse else "?"

            print(
                f"  {marker}{ch:<2} {servo.joint_name:<14} "
                f"{slack:>8} {taut:>8} {curled:>8} {status:<10}"
            )
        print()

    def _warmup_cycle(self, channel: int):
        """Run warm-up cycle to reach thermal equilibrium."""
        servo = self.calibration.servos.get(str(channel))
        if not servo:
            return

        print("  Running warm-up cycle (3 iterations)...")

        for i in range(3):
            print(f"    Cycle {i + 1}/3...", end="", flush=True)

            # Move to min
            self._set_pulse(channel, servo.pulse_min)
            time.sleep(0.3)

            # Move to max
            self._set_pulse(channel, servo.pulse_max)
            time.sleep(0.3)

            # Return to center
            center = (servo.pulse_min + servo.pulse_max) // 2
            self._set_pulse(channel, center)
            time.sleep(0.3)

            print(" done")

        self._current_pulse = (servo.pulse_min + servo.pulse_max) // 2
        print("  Warm-up complete\n")
        time.sleep(1)

    def _test_range(self, channel: int):
        """Test calibrated range of motion."""
        servo = self.calibration.servos.get(str(channel))
        if not servo or not servo.is_calibrated:
            print("  Joint not fully calibrated yet!")
            time.sleep(1)
            return

        print("  Testing: SLACK → TAUT → CURLED → TAUT")

        # To slack (approaching from below)
        print("    Moving to SLACK...", end="", flush=True)
        self._approach_from_below(channel, servo.slack_pulse)
        print(" done")
        time.sleep(0.5)

        # To taut
        print("    Moving to TAUT...", end="", flush=True)
        self._approach_from_below(channel, servo.taut_pulse)
        print(" done")
        time.sleep(0.5)

        # To curled
        print("    Moving to CURLED...", end="", flush=True)
        self._set_pulse(channel, servo.curled_pulse)
        print(" done")
        time.sleep(0.5)

        # Back to taut
        print("    Returning to TAUT...", end="", flush=True)
        self._approach_from_below(channel, servo.taut_pulse)
        print(" done")

        self._current_pulse = servo.taut_pulse
        time.sleep(1)

    def run(self):
        """Run the calibration interface."""
        # Initialize to first channel's center position
        servo = self.calibration.servos.get(str(self._current_channel))
        if servo:
            self._current_pulse = (servo.pulse_min + servo.pulse_max) // 2
            self._set_pulse(self._current_channel, self._current_pulse)

        try:
            while True:
                self._print_header()
                self._print_summary()

                if self._unsaved_changes:
                    print("  [!] Unsaved changes")
                print("\n  Waiting for input...", end="", flush=True)

                key = getch()

                # Movement controls
                if key == "a":  # Decrease by 50
                    self._current_pulse -= 50
                    self._set_pulse(self._current_channel, self._current_pulse)

                elif key == "d":  # Increase by 50
                    self._current_pulse += 50
                    self._set_pulse(self._current_channel, self._current_pulse)

                elif key == "j":  # Decrease by 10
                    self._current_pulse -= 10
                    self._set_pulse(self._current_channel, self._current_pulse)

                elif key == "l":  # Increase by 10
                    self._current_pulse += 10
                    self._set_pulse(self._current_channel, self._current_pulse)

                # Position setting
                elif key == "1":  # Set SLACK
                    servo = self.calibration.servos.get(str(self._current_channel))
                    if servo:
                        servo.slack_pulse = self._current_pulse
                        self._unsaved_changes = True
                        print(f"\n  ✓ SLACK set to {self._current_pulse}µs")
                        time.sleep(0.5)

                elif key == "2":  # Set TAUT
                    servo = self.calibration.servos.get(str(self._current_channel))
                    if servo:
                        servo.taut_pulse = self._current_pulse
                        self._unsaved_changes = True
                        print(f"\n  ✓ TAUT set to {self._current_pulse}µs")
                        time.sleep(0.5)

                elif key == "3":  # Set CURLED
                    servo = self.calibration.servos.get(str(self._current_channel))
                    if servo:
                        servo.curled_pulse = self._current_pulse
                        self._unsaved_changes = True
                        print(f"\n  ✓ CURLED set to {self._current_pulse}µs")
                        time.sleep(0.5)

                # Navigation
                elif key == "n":  # Next channel
                    self._release(self._current_channel)
                    self._current_channel = (self._current_channel + 1) % NUM_CHANNELS
                    servo = self.calibration.servos.get(str(self._current_channel))
                    if servo:
                        self._current_pulse = (servo.pulse_min + servo.pulse_max) // 2
                        self._set_pulse(self._current_channel, self._current_pulse)

                elif key == "p":  # Previous channel
                    self._release(self._current_channel)
                    self._current_channel = (self._current_channel - 1) % NUM_CHANNELS
                    servo = self.calibration.servos.get(str(self._current_channel))
                    if servo:
                        self._current_pulse = (servo.pulse_min + servo.pulse_max) // 2
                        self._set_pulse(self._current_channel, self._current_pulse)

                # Utility
                elif key == "m":  # Middle
                    servo = self.calibration.servos.get(str(self._current_channel))
                    if servo:
                        self._current_pulse = (servo.pulse_min + servo.pulse_max) // 2
                        self._set_pulse(self._current_channel, self._current_pulse)

                elif key == "r":  # Release
                    self._release(self._current_channel)
                    print("\n  Servo released")
                    time.sleep(0.5)

                elif key == "t":  # Test
                    self._test_range(self._current_channel)

                elif key == "w":  # Warm-up
                    self._warmup_cycle(self._current_channel)

                elif key == "s":  # Save
                    save_calibration(self.calibration, self.output_path)
                    self._unsaved_changes = False
                    print(f"\n  ✓ Saved to {self.output_path}")
                    time.sleep(1)

                elif key == "q":  # Quit
                    if self._unsaved_changes:
                        print("\n\n  Save before quitting? [y/n]: ", end="", flush=True)
                        if getch().lower() == "y":
                            save_calibration(self.calibration, self.output_path)
                            print(f"\n  Saved to {self.output_path}")
                    break

        finally:
            print("\n\nReleasing all servos...")
            self._release_all()
            print("Done!")


def run_tendon_calibration(
    config_path: str = "data/calibration/mg996r_calibration.json",
) -> int:
    """
    Run the tendon calibration tool.

    Args:
        config_path: Path to existing calibration file

    Returns:
        Exit code (0 = success)
    """
    print("\n" + "=" * 60)
    print("  RUKA Tendon Calibration")
    print("=" * 60)
    print("\nRun this AFTER installing tendons!")
    print(f"Config: {config_path}\n")

    # Load existing calibration (must have pulse ranges from range_finder)
    try:
        calibration = load_calibration(config_path)
        print(f"✓ Loaded calibration with {len(calibration.servos)} servos")

        # Check if range calibration was done
        uncalibrated = []
        for ch, servo in calibration.servos.items():
            if servo.pulse_min == 750 and servo.pulse_max == 2250:
                uncalibrated.append(ch)

        if uncalibrated:
            print(f"\n⚠ Warning: Channels {uncalibrated} have default pulse ranges")
            print("  Run 'ruka-calibrate range' first for best results")
            input("  Press Enter to continue anyway...")

    except Exception as e:
        print(f"✗ Failed to load calibration: {e}")
        print("Run 'ruka-calibrate range' first to create calibration file")
        return 1

    # Create and run calibrator
    calibrator = TendonCalibrator(calibration, config_path)

    if not calibrator.connect():
        return 1

    print("\nPress any key to start calibration...")
    getch()

    calibrator.run()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(run_tendon_calibration())
