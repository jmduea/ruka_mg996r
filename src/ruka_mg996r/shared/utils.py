"""
Shared utility functions and classes for RUKA MG996R project.
"""

import sys

# ====================================================================================
# Cross-Platform getch Implementation
# ====================================================================================
try:
    import msvcrt

    def getch() -> str:
        """Get a single character from standard input (Windows)."""
        return msvcrt.getch().decode("utf-8")
except ImportError:
    import termios
    import tty

    def getch() -> str:
        """Get a single character from standard input (Unix)."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)  # type: ignore
        try:
            tty.setraw(fd)  # type: ignore
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)  # type: ignore
        return ch
