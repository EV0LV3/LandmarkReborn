"""``python -m landmark_emu.world`` - runs the world (zone) server."""

from __future__ import annotations

from ..shared.hosting import run_server


async def _start(configuration):
    from .server import WorldServer, WorldServerConfiguration

    server = WorldServer(WorldServerConfiguration.bind(configuration))
    await server.start()
    return server.stop


def main() -> None:
    run_server("LandmarkEmulator: Zone Server", "WorldServer.json", "WorldServer.log", _start)


if __name__ == "__main__":
    main()
