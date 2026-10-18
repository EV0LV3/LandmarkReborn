# LandmarkEmu server (Python)

Python 3.11+ port of the LandmarkEmu C# backend: the **Auth server** (with its web API),
the **World/Zone server** (with the gateway layer) and the **packet-capture parser**.
It targets the same client build (v0.695.1.132647) and speaks byte-identical packets.
Client 0.589.1.128895 is supported as well: it differs only in the end of `SendSelfToClient`,
which is written in that client's layout when the gateway login reports a `0.589.*` build.

## Setup

```sh
cd server
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e .[dev]
```

Copy the example configs and edit them:

```sh
copy AuthServer.example.json AuthServer.json
copy WorldServer.example.json WorldServer.json
```

Both servers also need the client's game data (as with the original) in `GameDataPath`
(default `gameData/`): `en_us_data.dat`, `ProfileDefinitions.txt` and `BlackListEntries.txt`.

### Database

`Provider` is `MySql` (as before) or `Sqlite`. The original ADO.NET style connection strings
work unchanged, and so do databases created by the C# server (same tables and columns).
Missing tables are created on startup. For a quick local setup without MySQL:

```json
"Database": {
  "Auth":      { "Provider": "Sqlite", "ConnectionString": "Data Source=lmemu_auth.db" },
  "Character": { "Provider": "Sqlite", "ConnectionString": "Data Source=lmemu_character.db" }
}
```

A full SQLAlchemy URL (`mysql+pymysql://user:pass@host/db`) is accepted as well.

## Running

```sh
python -m landmark_emu.auth      # UDP 20042 + web API (default http://0.0.0.0:5080)
python -m landmark_emu.world     # UDP 19000
```

(`landmark-auth` / `landmark-world` are installed as commands too.)

Each reads `AuthServer.json` / `WorldServer.json` from the working directory, or
`--config <file>`. As before, any key can be overridden with environment variables
(`Network__Port=20043`) or arguments (`--Network:Port 20043`, `Network:Port=20043`).
Logs go to the console and to `AuthServer.log` / `WorldServer.log`; levels are set with
`Logging:ConsoleLevel` / `Logging:FileLevel`.

The auth console accepts `account create <username> <password>`. Accounts can also be
created through the web API:

| Method | Path | Query | Result |
| --- | --- | --- | --- |
| GET | `/` | | `Hello World!` |
| POST | `/create` | `username`, `password` | `200 {"username","message"}`, `409` if taken |
| POST | `/authenticate` | `username`, `password` | `200 {"sessionKey","sessionKeyExpiration","message"}`, `403` on bad login |

For https, set `WebApi:BaseURI` to `https://...` and `WebApi:CertificateFile` /
`WebApi:CertificateKeyFile` to a PEM certificate and key.

### Packet parser

```sh
python -m landmark_emu.parser capture.pcapng --game-data gameData
```

Writes `PacketParse.txt` (and dumps large packets to `packets/`), like the original tool.
Takes pcap or pcapng captures with Ethernet framing; auth traffic is recognised by port 20042.

## Tests

```sh
pytest
```

* `test_golden.py` compares output byte-for-byte with vectors produced by the original
  C# code (see `tests/golden/README.md`).
* `test_end_to_end.py` runs both servers on SQLite and drives a fake game client through
  web API login, character creation and the zone handoff, then parses the captured traffic.

## Layout

| C# project | Python package |
| --- | --- |
| `LandmarkEmulator.Shared` (network, crypto, config, game tables) | `landmark_emu.shared` |
| `LandmarkEmulator.Database*` (EF Core) | `landmark_emu.shared.database` (SQLAlchemy) |
| `LandmarkEmulator.AuthServer` | `landmark_emu.auth` |
| `LandmarkEmulator.WebAPI` (ASP.NET) | `landmark_emu.webapi` (aiohttp) |
| `LandmarkEmulator.Gateway` | `landmark_emu.gateway` |
| `LandmarkEmulator.WorldServer` | `landmark_emu.world` |
| `LandmarkEmulator.Parser` | `landmark_emu.parser` |

Threads became asyncio: the UDP listener, the world tick, the per-session paced sender
and the deferred database "events" all run on one event loop, with blocking database
calls on a worker pool. Attribute/reflection based message registration became decorators
(`@auth_message`, `@auth_handler`, `@zone_message`, `@zone_handler`, ...).

Wire-format quirks of the original (fields read or written asymmetrically, the trailing
SendSelf bytes, the ack/sequence behaviour, ...) are kept on purpose, because the client
was tested against exactly those bytes; they are marked with comments.

## Behaviour changes from the C# server

These are deliberate fixes; the packets themselves are unchanged:

* **SendSelfToClient uses the character chosen at login.** The original always used the
  first non-deleted character on the account.
* A pending database call no longer stalls the whole world tick (the original spun on it);
  session events still complete in order. Name validation and character creation now query
  the database off the event loop, so their replies go out on the next tick.
* A malformed datagram is logged instead of stopping the UDP listener, a bad multi-packet
  can no longer loop forever, a failed send can no longer recurse, datagrams over 512 bytes
  are accepted, and a session's sender stops when it disconnects.
* Size fields count UTF-8 bytes rather than UTF-16 characters (identical for ASCII).
* The text-id reverse lookup is built lazily instead of hashing 1,000,000 ids at startup.
* Malformed lines in `en_us_data.dat` are skipped with a warning instead of aborting.
* The web API defaults to http (the C# default needed the ASP.NET dev certificate).
* SQLite support, `--config`, and per-server log file names were added.
