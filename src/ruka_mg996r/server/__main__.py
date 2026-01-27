"""
Entry point for RUKA MG996R server application.

Usage:
    uv run -m ruka.server
    # or after install:
    ruka-server
"""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RUKA MG996R Hand Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run without hardware (simulation mode)",
    )
    parser.add_argument(
        "--calibration",
        type=str,
        default="data/calibration/mg996r_calibration.json",
        help="Path to calibration file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    args = parser.parse_args()

    import os

    os.environ["RUKA_SIMULATE"] = str(args.simulate).lower()
    os.environ["RUKA_CALIBRATION_PATH"] = args.calibration
    os.environ["RUKA_LOG_LEVEL"] = args.log_level

    import uvicorn

    uvicorn.run(
        "ruka_mg996r.server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level.lower(),
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
