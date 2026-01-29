"""
Entry point for RUKA client application.

Usage:
    uv run -m ruka.client
    # or after install:
    ruka-client
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RUKA MG996R Hand Tracking Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--server",
        "-s",
        default="ws://raspberrypi.local:8000/ws/control",
        help="WebSocket server URL",
    )
    parser.add_argument(
        "--camera",
        "-c",
        type=int,
        default=0,
        help="Camera index for video capture",
    )
    parser.add_argument(
        "--hand",
        "-H",
        choices=["left", "right"],
        default="right",
        help="Hand to track",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Disable video preview window",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    args = parser.parse_args()

    import logging

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # implement client logic here using args.server, args.camera, args.hand, args.no_preview
    return 0


if __name__ == "__main__":
    sys.exit(main())
