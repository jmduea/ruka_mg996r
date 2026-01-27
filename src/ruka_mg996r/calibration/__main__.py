"""
Entry point for RUKA MG996R calibration tools.

Usage:
    uv run -m ruka_mg996r.calibration [options]
    # or after install:
    ruka-calibrate [command]
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RUKA MG996R Calibration Tools",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Calibration commands")

    # Range finder command
    range_parser = subparsers.add_parser(
        "range",
        help="Calibrate the range of servo channels",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    range_parser.add_argument(
        "--channels",
        type=str,
        default=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        help="Comma-separated list of channels to calibrate (default: 0-10)",
    )
    range_parser.add_argument(
        "--output",
        "-o",
        default="data/calibration/mg996r_calibration.json",
        help="Output calibration file path",
    )

    # Tendon calibration command
    tendon_parser = subparsers.add_parser(
        "tendon",
        help="Calibrate tendon positions (run after tendon installation)",
    )
    tendon_parser.add_argument(
        "--config",
        "-c",
        default="data/calibration/mg996r_calibration.json",
        help="Existing calibration file to update",
    )

    # Test command
    test_parser = subparsers.add_parser(
        "test",
        help="Test calibration by moving through range",
    )
    test_parser.add_argument(
        "--config",
        "-c",
        default="data/calibration/mg996r_calibration.json",
        help="Calibration file to use for testing",
    )
    test_parser.add_argument(
        "--channel",
        type=int,
        default=None,
        help="Specific channel to test (default: all channels)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # TODO: Add range, tendon, test command implementations

    return 0


if __name__ == "__main__":
    sys.exit(main())
