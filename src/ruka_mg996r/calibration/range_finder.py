"""
MG996R Individual Servo Range Finder
"""

import logging
import time

from adafruit_servokit import ServoKit

from ruka_mg996r.server.config import (
    get_default_calibration,
    load_calibration,
    save_calibration,
)
from ruka_mg996r.shared import NUM_CHANNELS
from ruka_mg996r.shared.constants import (
    DEFAULT_CALIBRATION_PATH,
    DEFAULT_PULSE_CENTER,
    DEFAULT_PULSE_MAX,
    DEFAULT_PULSE_MIN,
    JOINT_NAMES,
    MG996R_SAFE_PULSE_MAX,
    MG996R_SAFE_PULSE_MIN,
    THUMB_CHANNELS,
)
from ruka_mg996r.shared.types import CalibrationData, ServoCalibration

logger = logging.getLogger(__name__)

TEST_STEP = 25  # microseconds per step


def find_servo_range(kit: ServoKit, channel: int) -> tuple[int, int]:
    """
    Slowly expand pulse range until servo stops responding to find true min and max pulse.

    Returns:
        (min_pulse, max_pulse)
    """
    print(f"\n{'=' * 50}")
    print(f"  Channel {channel} - {JOINT_NAMES.get(channel, 'unknown')}")
    print(f"{'=' * 50}\n")
    print("Watch the servo horn carefully as it moves.")
    print("note when it STOPS moving.")
    print("Press Enter to continue, 'q' to quit early.\n")

    # Start from center
    kit.servo[channel].set_pulse_width_range(DEFAULT_PULSE_MIN, DEFAULT_PULSE_MAX)
    kit.servo[channel].angle = 90
    time.sleep(1.0)

    # Find minimum (searching downward from center)
    print("--- Finding MINIMUM pulse ---")
    current_pulse = DEFAULT_PULSE_CENTER
    true_min = MG996R_SAFE_PULSE_MIN  # fallback
    last_working_pulse = current_pulse

    while current_pulse > MG996R_SAFE_PULSE_MIN:
        # Decrese pulse by TEST_STEP microseconds
        current_pulse -= TEST_STEP
        kit.servo[channel].set_pulse_width_range(current_pulse, DEFAULT_PULSE_MAX)
        kit.servo[channel].angle = 0  # Go to new 'minimum'
        time.sleep(0.3)

        response = (
            input(f" Pulse {current_pulse}us - Did the servo move? (y/n/q): ")
            .strip()
            .lower()
        )

        if response == "n":
            true_min = last_working_pulse  # last working value
            print(f" Minimum found at {true_min}us\n")
            break
        elif response == "q":
            true_min = last_working_pulse
            print(f" Minimum set to: {true_min}us (quit early)")
            break
        else:
            last_working_pulse = current_pulse

    # Return to center
    kit.servo[channel].set_pulse_width_range(DEFAULT_PULSE_MIN, DEFAULT_PULSE_MAX)
    kit.servo[channel].angle = 90
    time.sleep(0.5)

    print("\n--- Finding MAXIMUM pulse ---")
    current_pulse = DEFAULT_PULSE_CENTER
    true_max = MG996R_SAFE_PULSE_MAX
    last_working_pulse = current_pulse

    while current_pulse < MG996R_SAFE_PULSE_MAX:
        current_pulse += TEST_STEP
        kit.servo[channel].set_pulse_width_range(DEFAULT_PULSE_MIN, current_pulse)
        kit.servo[channel].angle = 180  # Go to new 'maximum'
        time.sleep(0.3)

        response = (
            input(f" Pulse {current_pulse}us - Did the servo move? (y/n/q): ")
            .strip()
            .lower()
        )

        if response == "n":
            true_max = last_working_pulse  # last working value
            print(f" Maximum found at {true_max}us\n")
            break
        elif response == "q":
            true_max = last_working_pulse
            print(f" Maximum set to: {true_max}us (quit early)")
            break
        else:
            last_working_pulse = current_pulse

    # Calc new center
    usable_range = true_max - true_min

    print(f"=== Channel {channel} Results:")
    print(f"    Min: {true_min}us")
    print(f"    Max: {true_max}us")
    print(f"    Range: {usable_range}us (~180 degrees)\n")

    # Return to center and release
    kit.servo[channel].set_pulse_width_range(true_min, true_max)
    kit.servo[channel].angle = 90
    time.sleep(0.5)
    kit.servo[channel].angle = None

    return true_min, true_max


def get_open_pulse(channel: int, pulse_min: int, pulse_max: int) -> int:
    """
    Get the pulse width for the fully open (relaxed) position.

    - Thumb servos: clockwise to close → open is at MAX pulse
    - Finger servos: counter-clockwise to close → open is at MIN pulse
    """
    if channel in THUMB_CHANNELS:
        return pulse_max
    else:
        return pulse_min


def set_all_servos_to_open(kit: ServoKit, calibration: CalibrationData) -> None:
    """
    Set all calibrated servos to their fully open position.
    This is the starting position before tendon installation.
    """
    print("\n" + "=" * 60)
    print("  Setting all servos to OPEN position")
    print("=" * 60)
    print("\n  Thumb servos (ch 8-10): rotating to MAX pulse (open/180°)")
    print("  Finger servos (ch 0-7): rotating to MIN pulse (open/0°)\n")

    for ch_str in sorted(calibration.servos.keys()):
        ch = int(ch_str)
        servo = calibration.servos[ch_str]
        open_pulse = get_open_pulse(ch, servo.pulse_min, servo.pulse_max)

        # Set pulse range and move to open position
        kit.servo[ch].set_pulse_width_range(servo.pulse_min, servo.pulse_max)

        # Calculate angle: 0° for min pulse, 180° for max pulse
        if ch in THUMB_CHANNELS:
            angle = 180  # Max pulse = open for thumb
        else:
            angle = 0  # Min pulse = open for fingers

        kit.servo[ch].angle = angle

        direction = "thumb" if ch in THUMB_CHANNELS else "finger"
        print(
            f"  Ch {ch:2d} ({servo.joint_name:12s}): {direction:6s} → {open_pulse}µs (angle={angle}°)"
        )
        time.sleep(0.2)  # Small delay between servos

    print("\n  All servos set to open position.")
    input("  Press Enter to release servos and finish...")


def run_range_finder(
    channels: str | None = None,
    output_path: str = DEFAULT_CALIBRATION_PATH,
) -> int:
    """
    Run the servo range finder.

    Args:
        channels (str | None): Comma-separated list of channels to calibrate (default: 0-10)
        output_path (str): Path to save calibration JSON file.

    Returns:
        int: Exit code (0=success, 1=failure)
    """
    print(f"\n {'=' * 60}")
    print("  MG996R Servo Range Finder")
    print(f" {'=' * 60}\n")
    print("\nRun this BEFORE installing tendons to avoid damage.\n")
    print(f"Output: {output_path}\n")

    # parse channels to find servo range for
    if channels:
        channel_list = [int(ch.strip()) for ch in channels.split(",")]
    else:
        channel_list = list(range(NUM_CHANNELS))  # Default channels 0-10

    print(f"Channels to calibrate: {channel_list}\n")

    # Load existing calibration or create new
    try:
        calibration = load_calibration(output_path)
        print("Loaded existing calibration.")
    except FileNotFoundError:
        calibration = get_default_calibration()
        print("Starting fresh calibration.")

    # Try connecting to hardware
    try:
        from adafruit_servokit import ServoKit

        kit = ServoKit(channels=16)
        print("SUCCESS: Connected to PCA9685\n")
    except ImportError:
        print("ERROR: adafruit_servokit library not found.")
        print("Install with: uv sync --extra calibration")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to connect to PCA9685: {e}")
        print("\nMake sure you are running on the Raspberry Pi with PCA9685 connected.")
        return 1

    # Main calibration loop
    try:
        for channel in channel_list:
            user_input = input(
                f"\nPress Enter to calibrate {channel} ({JOINT_NAMES.get(channel, 'unknown joint')} (or 'q' to quit, 's' to skip))..."
            ).strip().lower()
            
            if user_input in ('q', 'exit', 'quit'):
                print("\nExiting calibration loop...")
                break
            
            if user_input == "s":
                print(f"Skipping channelk {channel}...")
                continue

            min_pulse, max_pulse = find_servo_range(kit, channel)

            # update calibration data
            joint_name = JOINT_NAMES.get(channel, f"channel_{channel}")
            curl_direction = channel not in THUMB_CHANNELS  # thumb curls opposite

            if str(channel) in calibration.servos:
                servo = calibration.servos[str(channel)]
                servo.pulse_min = min_pulse
                servo.pulse_max = max_pulse
                servo.curl_direction_positive = curl_direction
            else:
                calibration.servos[str(channel)] = ServoCalibration(
                    channel=channel,
                    joint_name=joint_name,
                    pulse_min=min_pulse,
                    pulse_max=max_pulse,
                    curl_direction_positive=curl_direction,
                )

            # save updated calibration
            save_calibration(calibration, output_path)

    except KeyboardInterrupt:
        print("\n\n!!!  Calibration interrupted")
        save_response = input("Save progress? (y/n): ").strip().lower()
        if save_response == "y":
            save_calibration(calibration, output_path)

    print("\nRange finding complete.")
    set_all_servos_to_open(kit, calibration)
    print("\nReleasing all servos...")
    for ch in range(16):
        try:
            kit.servo[ch].angle = None
        except Exception:
            pass

    print(f"\n {'=' * 60}")
    print("  CALIBRATION SUMMARY")
    print(f" {'=' * 60}\n")
    print(f"\n  {'Ch':<4} {'Joint':<16} {'Min':>6} {'Max':>6} {'Range':>8}")
    print(f" {'-' * 44}")

    if not calibration.servos:
        print("  No servos calibrated yet.")
    else:
        for ch in sorted(calibration.servos.keys()):
            servo = calibration.servos[ch]
            range_us = servo.pulse_max - servo.pulse_min
            print(
                f"  {servo.channel:<4} {servo.joint_name:<16} "
                f"{servo.pulse_min:>6} {servo.pulse_max:>6} {range_us:>6}us"
            )

    print(f"\nCalibration saved to: {output_path}")
    print("Next steps:")
    print("  1. Install tendons (finish mechanical assembly)")
    print("  2. Run: uv run ruka-calibrate tendon")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(run_range_finder())
