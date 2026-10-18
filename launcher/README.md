# Landmark RE:Build launcher (Tauri 2)

Replaces the WPF `LandmarkEmulator.Launcher`. It logs in through the auth server's web API
and starts `Landmark64.exe` with the session key:

```
Landmark64.exe SessionId=<key> CasSessionId=0 STEAM_ENABLED=0
```

## Requirements

* Rust (stable) and Node.js 18+
* Windows: the WebView2 runtime (preinstalled on Windows 10/11)
* Linux/macOS: the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)

## Develop / build

```sh
cd launcher
npm install
npm run dev        # run with hot reload of the HTML/JS
npm run build      # release build + installers in src-tauri/target/release/bundle
```

Rust unit tests: `cd src-tauri && cargo test`.

## Configuration

`LauncherConfig.json` (same format as the original):

```json
{ "Server": "http://127.0.0.1:5080" }
```

If a `LauncherConfig.json` sits next to the launcher executable it is used (portable
install); otherwise the file lives in the per-user config directory
(`%APPDATA%\com.landmarkemu.launcher` on Windows) and is created on first run. The path is
shown as a tooltip on the server line at the bottom of the window.

The game location is asked for the first time you press **Play** and is remembered as
`GamePath` in the same file; use **Change game location** to pick it again.

## Client 0.589 allocator fix

The Steam client (0.589.1.128895) hangs at ~50% of the loading screen ("Not Responding") on CPUs
with many hardware threads. Its memory manager has 64 per-thread heap slots; with enough cores the
game starts more allocating threads than that, and every thread left without a slot rescans all 64
slots (OpenThread / GetExitCodeThread / CloseHandle per slot) under the global allocator lock on
*every* allocation. The main thread and the terrain threads starve on that lock.

The launcher therefore starts the game suspended, replaces the rescan with "no slot" (3 bytes at
`Landmark64.exe+0x2B6B8C1`: `48 8B FE` → `EB 76 90`, so such threads use the shared allocator
path), and resumes it. Only the process memory is changed, never the file, and only when those
bytes match, so other builds start unmodified. See `src-tauri/src/game_patch.rs`.

To check it against a client without running the game:
`LANDMARK_EXE=<path>\Landmark64.exe cargo test -- --ignored patches_suspended_client`.

## Differences from the WPF launcher

* The game location is remembered between runs.
* The session expiry from the server is honoured: Play only re-authenticates when the key
  has (nearly) expired. The original re-authenticated on every Play.
* Credentials are URL-encoded, so passwords containing `&`, `+`, `#`, ... work.
* Errors are shown in the window instead of message boxes.
