# LandmarkReborn (Python + Tauri)

> [!IMPORTANT]
> The world is loading, but there is still a lot of work to be done. The travel system is not working, etc.

A port of [LandmarkEmu](https://github.com/kirmmin/LandmarkEmu), the server emulator for the
sunset MMORPG Landmark:

| Folder | What | Replaces |
| --- | --- | --- |
| [`server/`](server/README.md) | Python 3.11+ Auth server + web API, World/Zone server, packet parser | the C# `.sln` (AuthServer, WorldServer, Gateway, WebAPI, Database*, Shared, Parser) |
| [`launcher/`](launcher/README.md) | Tauri 2 (Rust) desktop launcher | `LandmarkEmulator.Launcher` (WPF) |

## Quick start (local, no MySQL)

```sh
cd server
python -m venv .venv && .venv\Scripts\activate
pip install -e .[dev]
copy AuthServer.example.json AuthServer.json     # set Database.*.Provider to "Sqlite", see server/README.md
copy WorldServer.example.json WorldServer.json
# put en_us_data.dat, ProfileDefinitions.txt, BlackListEntries.txt in server/gameData/
python -m landmark_emu.auth        # terminal 1  ->  account create <user> <password>
python -m landmark_emu.world       # terminal 2

cd ../launcher
npm install
npm run dev                         # log in, press Play, pick Landmark64.exe
```

The servers are wire-compatible with the original: the test suite checks the Python output
byte-for-byte against vectors generated from the original C# code, and runs a full
login → character creation → zone login flow with a simulated client.

Licensed under the GNU AGPL v3, like the original.

###### Landmark, EverQuest, Daybreak Games, and all associated logos and designs are trademarks or registered trademarks of Daybreak Games. All other trademarks are the property of their respective owners.

###### AI is use to convert it to Python and Rust!
