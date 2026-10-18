"""``python -m landmark_emu.auth`` - runs the auth server (and its web API)."""

from __future__ import annotations

from ..shared.hosting import run_server
from .config import AuthServerConfiguration


async def _start(configuration):
    from .server import AuthServer

    server = AuthServer(AuthServerConfiguration.bind(configuration))
    await server.start()
    return server.stop


def main() -> None:
    run_server("LandmarkEmulator: Auth Server", "AuthServer.json", "AuthServer.log", _start)


if __name__ == "__main__":
    main()
