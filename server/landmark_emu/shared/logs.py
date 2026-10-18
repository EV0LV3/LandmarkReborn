"""Logging configuration mirroring the original NLog layout:

    [HH:mm:ss]: [LEVEL][Logger] message
"""

from __future__ import annotations

import logging
import os
import sys

TRACE = 5
logging.addLevelName(TRACE, "TRACE")

_LEVEL_COLOURS = {
    TRACE: "\x1b[90m",
    logging.DEBUG: "\x1b[90m",
    logging.INFO: "\x1b[97m",
    logging.WARNING: "\x1b[93m",
    logging.ERROR: "\x1b[91m",
    logging.CRITICAL: "\x1b[97;41m",
}
_RESET = "\x1b[0m"

_FORMAT = "[%(asctime)s]: [%(levelname)s][%(name)s] %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def enable_ansi_console() -> None:
    """Turn on VT escape processing for the Windows console (no-op elsewhere)."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


class _ColourFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        colour = _LEVEL_COLOURS.get(record.levelno)
        return f"{colour}{text}{_RESET}" if colour else text


def parse_level(value: str | int | None, default: int) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    name = str(value).strip().upper()
    if name == "TRACE":
        return TRACE
    if name in ("WARN", "WARNING"):
        return logging.WARNING
    if name == "FATAL":
        return logging.CRITICAL
    level = logging.getLevelName(name)
    return level if isinstance(level, int) else default


def configure_logging(log_file: str | None, console_level: int = logging.DEBUG, file_level: int = TRACE) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.setLevel(min(console_level, file_level) if log_file else console_level)

    enable_ansi_console()
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(_ColourFormatter(_FORMAT, _DATE_FORMAT))
    root.addHandler(console)

    if log_file:
        # The original deletes the previous log on startup.
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(logging.Formatter(_FORMAT, _DATE_FORMAT))
        root.addHandler(file_handler)

    # Keep third-party chatter at a sensible level.
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def hex_dump(data: bytes) -> str:
    """``BitConverter.ToString`` style: uppercase bytes separated by dashes."""
    return data.hex("-").upper()
