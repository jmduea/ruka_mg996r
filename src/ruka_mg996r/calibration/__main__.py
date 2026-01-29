"""
Entry point for RUKA MG996R calibration tools.

Usage:
    uv run -m ruka_mg996r.calibration [command]
    # or after install:
    ruka-calibrate [command]

Commands:
    range   - Calibrate the range of servo channels
    tendon  - Calibrate tendon positions (run after tendon installation)
    test    - Test calibration by moving through range
"""

import argparse
import logging
import sys


def cmd_range(args) -> int:
    """Run the range finder calibration tool."""
    from ruka_mg996r.calibration.range_finder import run_range_finder

    return run_range_finder(args.channels, args.output)

    # def cmd_tendon(args) -> int:
    """Run the tendon calibration tool."""
    # from ruka_mg996r.calibration.tendon_calibrator import run_tendon_calibrator

    # return run_tendon_calibrator(args.config)

    # def cmd_test(args) -> int:
    """Test calibration."""
    # from ruka_mg996r.calibration.calibration_tester import run_calibration_tester

    # return run_calibration_tester(args.config, args.channel)


def main() -> int:
    """Main entry point for calibration tools."""
    parser = argparse.ArgumentParser(
        description="RUKA MG996R Calibration Tools",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""
Commands:
    range   Find servo pulse width ranges (use before tendon installation)
    tendon  Calibrate tendon positions (use AFTER tendon installation)
    test    Test calibration by moving through range

Examples:
    uv run ruka-calibrate range                     # Find ranges for all channels
    uv run ruka-calibrate range --channels 0,1,2    # Find ranges for specific channels
    uv run ruka-calibrate tendon                    # Calibrate tendons
    uv run ruka-calibrate test                      # Test all channels
    uv run ruka-calibrate test --channel 3          # Test specific channel
        """,
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
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
        "-c",
        type=str,
        default=None,
        help="Comma-separated list of channels to calibrate (default: 0-10)",
    )
    range_parser.add_argument(
        "--output",
        "-o",
        default="data/calibration/mg996r_calibration.json",
        help="Output calibration file path",
    )
    range_parser.set_defaults(func=cmd_range)

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
    # tendon_parser.set_defaults(func=cmd_tendon)

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
    # test_parser.set_defaults(func=cmd_test)

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
