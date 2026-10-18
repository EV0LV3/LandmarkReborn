"""Process entry helpers shared by the server executables."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from collections.abc import Awaitable, Callable

from .config import Configuration, ConfigurationException, resolve_config_file
from .logs import TRACE, configure_logging, parse_level

log = logging.getLogger("Host")


def set_console_title(title: str) -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(title)
            return
        except Exception:
            pass
    if sys.stdout.isatty():
        sys.stdout.write(f"\x1b]0;{title}\x07")
        sys.stdout.flush()


def load_configuration(default_file: str) -> Configuration:
    path = resolve_config_file(default_file)
    try:
        return Configuration.load(path)
    except ConfigurationException as exc:
        sys.stderr.write(
            f"{exc}\nCopy the matching *.example.json to {default_file} (or pass --config <file>) and edit it.\n"
        )
        raise SystemExit(1) from exc


def run_server(
    title: str,
    default_config_file: str,
    log_file: str,
    start: Callable[[Configuration], Awaitable[Callable[[], Awaitable[None]]]],
) -> None:
    """Load config, configure logging, start the server and run until Ctrl+C."""
    configuration = load_configuration(default_config_file)
    configure_logging(
        log_file,
        console_level=parse_level(configuration.get_str("Logging:ConsoleLevel"), logging.DEBUG),
        file_level=parse_level(configuration.get_str("Logging:FileLevel"), TRACE),
    )
    set_console_title(title)

    async def main() -> None:
        loop = asyncio.get_running_loop()
        stop_requested = asyncio.Event()

        def request_stop(*_args) -> None:
            loop.call_soon_threadsafe(stop_requested.set)

        # Ctrl+C, Ctrl+Break (Windows) and service-manager termination all shut down cleanly.
        for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), request_stop)

        stop = await start(configuration)
        try:
            await stop_requested.wait()
        finally:
            await stop()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        log.critical("Fatal error", exc_info=True)
        raise SystemExit(1)
