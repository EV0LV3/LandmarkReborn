"""Interactive console commands read from stdin on a background thread."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Protocol

log = logging.getLogger("CommandManager")

# ConsoleColor names used in command output markup ("{=Red}text").
_COLOURS = {
    "black": "30", "darkblue": "34", "darkgreen": "32", "darkcyan": "36", "darkred": "31",
    "darkmagenta": "35", "darkyellow": "33", "gray": "37", "darkgray": "90", "blue": "94",
    "green": "92", "cyan": "96", "red": "91", "magenta": "95", "yellow": "93", "white": "97",
    "orange": "38;5;208",
}


def write_markup(message: str) -> None:
    """Print text containing ``{=Colour}`` / ``{/}`` markup."""
    out = []
    for segment in message.replace("}", "{").split("{"):
        if not segment:
            continue
        if segment.startswith("/"):
            out.append("\x1b[0m")
        elif segment.startswith("=") and segment[1:].lower() in _COLOURS:
            out.append(f"\x1b[{_COLOURS[segment[1:].lower()]}m")
        else:
            out.append(segment + "\x1b[0m\n")
    sys.stdout.write("".join(out))
    sys.stdout.flush()


class CommandHandler(Protocol):
    def invoke(self, command: str) -> None: ...


class CommandManager:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._handler: CommandHandler | None = None
        self._stop = threading.Event()

    def initialise(self, handler: CommandHandler) -> None:
        self._handler = handler
        self._thread = threading.Thread(target=self._run, name="commands", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        log.info("Started command thread.")
        while not self._stop.is_set():
            try:
                line = input(">> ")
            except EOFError:
                break
            except Exception:
                log.exception("Failed to read command")
                break
            if not line.strip():
                continue
            try:
                self._handler.invoke(line)
            except Exception:
                log.exception("Command failed")
        log.info("Stopped command thread.")

    def shutdown(self) -> None:
        self._stop.set()
