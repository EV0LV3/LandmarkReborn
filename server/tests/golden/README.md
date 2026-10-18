# Golden vectors

`golden.json` holds byte-level reference output produced by the **original C# server code**:
RC4, CRC, Jenkins hashes, PBKDF2 verifiers, stream fragmentation/reassembly, protocol packets,
every Auth reply, zone opcode framing, the 735 KB ArtData packet and a full read→write round
trip of the captured 655 KB `SendSelfToClient` packet. `test_golden.py` asserts the Python
port produces identical bytes.

The tests only need the JSON. To regenerate it you need the .NET 6 SDK and a checkout of the
original repository (by default `../../../../_original`, i.e. next to `server/`):

```sh
cd server/tests/golden/harness
dotnet build -c Release            # add -p:OriginalRoot=<path> for a different checkout
dotnet bin/Release/net6.0/Golden.dll ../../../landmark_emu/resources/<dir> ../golden.json
```

The first argument is a directory containing `ArtTints.json` and `SendSelf.bin`
(copy them from `landmark_emu/resources/auth` and `landmark_emu/resources/world/PacketDumps`).
