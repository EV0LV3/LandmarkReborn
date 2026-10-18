using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text;
using ICSharpCode.SharpZipLib.Zip.Compression.Streams;
using LandmarkEmulator.AuthServer.Network.Message;
using LandmarkEmulator.AuthServer.Network.Message.Model;
using LandmarkEmulator.AuthServer.Network.Message.Model.TunnelData;
using LandmarkEmulator.AuthServer.Network.Message.Static;
using LandmarkEmulator.AuthServer.Network.Packets;
using LandmarkEmulator.AuthServer.Zone;
using LandmarkEmulator.Database.Auth.Model;
using LandmarkEmulator.Shared.Game;
using LandmarkEmulator.Shared.Game.Entity.Static;
using LandmarkEmulator.Shared.GameTable.Text;
using LandmarkEmulator.Shared.Network;
using LandmarkEmulator.Shared.Network.Cryptography;
using LandmarkEmulator.Shared.Network.Message;
using LandmarkEmulator.Shared.Network.Message.Model;
using LandmarkEmulator.Shared.Network.Message.Model.Shared;
using LandmarkEmulator.Shared.Network.Packets;
using LandmarkEmulator.WorldServer.Network;
using LandmarkEmulator.WorldServer.Network.Message;
using LandmarkEmulator.WorldServer.Network.Message.Model;
using LandmarkEmulator.WorldServer.Network.Packets;
using Newtonsoft.Json;

static class Program
{
    static string Hex(byte[] b) => Convert.ToHexString(b);
    static string Sha(byte[] b) => Convert.ToHexString(SHA256.HashData(b));

    static byte[] Game(IWritable m)
    {
        var l = new List<byte>();
        m.Write(new GamePacketWriter(l));
        return l.ToArray();
    }

    static byte[] ProtocolSend(IProtocol message, ProtocolMessageOpcode opcode, bool useEncryption, PacketOptions options)
    {
        var packet = new ProtocolPacket(opcode, message, useEncryption, options);
        var data = new List<byte>();
        var writer = new ProtocolPacketWriter(data);
        writer.Write((ushort)packet.Opcode);
        writer.WriteBytes(packet.Data);
        var bytes = data.ToArray();
        if (packet.UseEncryption)
            bytes = CrcProvider.AppendCRC(bytes, 0);
        return bytes;
    }

    static byte[] Auth(AuthMessageOpcode opcode, IWritable message)
    {
        var p = new AuthPacket(opcode, message);
        return new[] { (byte)opcode }.Concat(p.Data).ToArray();
    }

    static byte[] Seq(int n, int mul, int add) => Enumerable.Range(0, n).Select(i => (byte)((i * mul + add) & 0xFF)).ToArray();

    static void Main(string[] args)
    {
        string resources = args[0];
        string outFile = args[1];
        var g = new Dictionary<string, object>();

        // ---------------- crypto ----------------
        var key = Convert.FromBase64String("F70IaxuU8C/w7FPXY1ibXw==");
        var arc = new Arc4Provider(key);
        var a1 = Encoding.ASCII.GetBytes("hello world");
        arc.Encrypt(a1);
        var a2 = Seq(1000, 1, 0);
        arc.Encrypt(a2);
        var arc2 = new Arc4Provider(Seq(16, 13, 7));
        var a3 = Seq(64, 3, 1);
        arc2.Encrypt(a3);
        g["arc4"] = new { first = Hex(a1), second = Hex(a2), other_key = Hex(Seq(16, 13, 7)), other_plain = Hex(Seq(64, 3, 1)), other = Hex(a3) };

        var crcData = Seq(300, 7, 0);
        var crcs = new Dictionary<string, uint>();
        foreach (var seed in new[] { 0, 1, 0x12345678, -1, 255 })
            crcs[seed.ToString()] = CrcProvider.crc32(ref crcData, seed);
        g["crc"] = new { data = Hex(crcData), seeds = crcs, append = Hex(CrcProvider.AppendCRC(crcData.Take(10).ToArray(), 0)) };

        var jenkins = new Dictionary<string, uint>();
        foreach (var s in new[] { "", "a", "ab", "abcdefghijk", "abcdefghijkl", "abcdefghijklm", "Global.Text.62147", "Global.Text.0", "Global.Text.571666", "Global.Text.999999", "abcdefghijklmnopqrstuvwxyz0123456789", "Ünïcødé" })
            jenkins[s] = JenkinsLookup2.Lookup(s);
        g["jenkins"] = jenkins;
        g["text_hash"] = new Dictionary<string, uint>
        {
            ["62147"] = TextManager.Instance.GetHash(62147u),
            ["Global.Text.5"] = TextManager.Instance.GetHash("Global.Text.5"),
            ["Foo"] = TextManager.Instance.GetHash("Foo"),
        };

        var (salt, verifier) = PasswordProvider.GenerateSaltAndVerifier("hunter2", Seq(16, 1, 1));
        g["password"] = new { password = "hunter2", salt, verifier };

        var twoBit = new Dictionary<string, string>();
        foreach (var v in new[] { 0, 1, 63, 64, 1000, 16383, 16384, 4194303, 4194304, 100000000 })
        {
            var l = new List<byte>();
            new GamePacketWriter(l).WriteUIntWith2BitLength(v);
            twoBit[v.ToString()] = Hex(l.ToArray());
        }
        g["uint_2bit"] = twoBit;
        var twoBitRead = new Dictionary<string, uint>();
        foreach (var h in new[] { "00", "04", "FD00", "0101", "FE0100", "FF010203" })
            twoBitRead[h] = new GamePacketReader(Convert.FromHexString(h)).ReadUInt2BitLength();
        g["uint_2bit_read"] = twoBitRead;

        // ---------------- data stream output ----------------
        var outEvents = new List<object>();
        var dso = new DataStreamOutput(null);
        dso.OnData += (seq, pkt, ooo) => outEvents.Add(new { seq = (int)seq, frag = pkt.IsFragment, ooo, data = Hex(pkt.Data) });
        dso.SetFragmentSize(505);
        var outInputs = new List<string>();
        void Pack(byte[] d) { outInputs.Add(Hex(d)); dso.PackData(d.ToArray()); }
        Pack(Encoding.ASCII.GetBytes("small packet"));
        Pack(Seq(1500, 1, 0));
        Pack(Seq(505, 5, 3));
        Pack(Seq(506, 5, 3));
        dso.SetEncryption(false);
        Pack(new byte[] { 0, 1, 2, 3 });
        dso.SetEncryption(true);
        Pack(Seq(40, 11, 2));
        dso.HandleAck(3);
        var missingAfterAck = dso.MissingAcks;
        dso.ResendData(5);
        g["stream_out"] = new { fragment_size = 505, inputs = outInputs, events = outEvents, ack = 3, missing_acks_after_ack = missingAfterAck };

        // ---------------- data stream input ----------------
        var inEvents = new List<string>();
        var inAcks = new List<int>();
        var dsi = new DataStreamInput(null);
        dsi.OnData += d => inEvents.Add(Hex(d));
        var feed = new List<object>();
        void Feed(ushort seq, byte[] data, bool fragment)
        {
            feed.Add(new { seq = (int)seq, frag = fragment, data = Hex(data) });
            if (fragment) dsi.ProcessDataFragment(new DataFragment { Sequence = seq, Data = data });
            else dsi.ProcessDataFragment(new DataWhole { Sequence = seq, Data = data });
            inAcks.Add(dsi.LastAck.HasValue ? dsi.LastAck.Value : -1);
        }
        Feed(0, Seq(20, 3, 9), false);
        var multi = new List<byte> { 0x00, 0x19, 0x03, 0xAA, 0xBB, 0xCC, 0xFF, 0x01, 0x2C };
        multi.AddRange(Seq(300, 7, 1));
        multi.AddRange(new byte[] { 0x02, 0x00, 0x00 });
        Feed(1, multi.ToArray(), false);
        Feed(2, new byte[] { 0x00, 0x00, 0x11, 0x22, 0x33 }, false);
        var first = new List<byte> { 0x00, 0x00, 0x03, 0xE8 };
        first.AddRange(Seq(400, 1, 5));
        Feed(3, first.ToArray(), true);
        Feed(4, Seq(400, 1, 6), true);
        Feed(5, Seq(200, 1, 7), true);
        Feed(7, Seq(10, 2, 0), false);
        Feed(6, Seq(10, 2, 1), false);
        Feed(8, Seq(10, 2, 2), false);
        g["stream_in"] = new { feed, outputs = inEvents, last_acks = inAcks };

        // ---------------- protocol messages ----------------
        var proto = new Dictionary<string, string>
        {
            ["session_reply"] = Hex(ProtocolSend(new SessionReply { SessionId = 0xDEADBEEF, CRCSeed = 0, CRCLength = 2, Compression = 0x100, UdpLength = 512 }, ProtocolMessageOpcode.SessionReply, true, new PacketOptions { Compression = true })),
            ["ack"] = Hex(ProtocolSend(new Ack { Sequence = 5 }, ProtocolMessageOpcode.Ack, true, new PacketOptions())),
            ["ack_sub"] = Hex(ProtocolSend(new Ack { Sequence = 0x1234 }, ProtocolMessageOpcode.Ack, true, new PacketOptions { IsSubpacket = true })),
            ["out_of_order"] = Hex(ProtocolSend(new OutOfOrder { Sequence = 9 }, ProtocolMessageOpcode.OutOfOrder, true, new PacketOptions { Compression = true })),
            ["data_compressed"] = Hex(ProtocolSend(new DataWhole { Sequence = 3, Data = Seq(20, 1, 0) }, ProtocolMessageOpcode.Data, true, new PacketOptions { Compression = true })),
            ["fragment_uncompressed"] = Hex(ProtocolSend(new DataFragment { Sequence = 65535, Data = Seq(20, 1, 1) }, ProtocolMessageOpcode.DataFragment, true, new PacketOptions { Compression = false })),
            ["ping"] = Hex(ProtocolSend(new Ping(), ProtocolMessageOpcode.Ping, true, new PacketOptions())),
            ["disconnect"] = Hex(ProtocolSend(new Disconnect(), ProtocolMessageOpcode.Disconnect, true, new PacketOptions { IsPriority = true })),
        };
        g["protocol"] = proto;

        // MultiPacket parsing (plain and zlib-compressed)
        var subs = new List<byte>();
        foreach (var sub in new[] { new byte[] { 0x00, 0x15, 0x00, 0x07 }, new byte[] { 0x00, 0x09, 0x00, 0x01, 0xDE, 0xAD } })
        {
            subs.Add((byte)sub.Length);
            subs.AddRange(sub);
        }
        var big = new List<byte> { 0x00, 0x09, 0x00, 0x02 };
        big.AddRange(Seq(300, 1, 0));
        subs.Add(0xFF); subs.Add((byte)(big.Count >> 8)); subs.Add((byte)big.Count);
        subs.AddRange(big);
        var plainMulti = new List<byte> { 0x00 };
        plainMulti.AddRange(subs);
        plainMulti.AddRange(new byte[] { 0xAB, 0xCD });
        var ms = new MemoryStream();
        using (var dos = new DeflaterOutputStream(ms)) dos.Write(subs.ToArray(), 0, subs.Count);
        var compressedMulti = new List<byte> { 0x01 };
        compressedMulti.AddRange(ms.ToArray());
        compressedMulti.AddRange(new byte[] { 0xAB, 0xCD });
        object ParseMulti(byte[] body)
        {
            var mp = new MultiPacket();
            mp.Read(new ProtocolPacketReader(body), new PacketOptions { Compression = true });
            return mp.Packets.Select(p => new { opcode = (int)p.Opcode, data = Hex(p.Data) }).ToList();
        }
        g["multi"] = new
        {
            plain = Hex(plainMulti.ToArray()),
            plain_packets = ParseMulti(plainMulti.ToArray()),
            compressed = Hex(compressedMulti.ToArray()),
            compressed_packets = ParseMulti(compressedMulti.ToArray()),
        };

        // ---------------- auth messages ----------------
        var payload = new CharacterSelectInfoReply.Character.CharacterPayload
        {
            Name = "Tester", Race = 1, Gender = 2, ProfileId = 46, ModelId = 392,
        };
        payload.Model.SkinId = 5; payload.Model.Race = 1; payload.Model.Gender = 2;
        payload.Model.Customisations.Add((1, 2, 3));
        payload.Model.Customisations.Add((4, 5, 6));
        payload.CharacterAttachments.Add(new CharacterSelectInfoReply.Character.CharacterPayload.CharacterAttachment
        {
            ModelName = "Char_Biped_[RACE][GENDER]_Entities_Colony_000_Chest.adr", Slot = AttachmentSlot.Head,
        });
        var select10 = new CharacterSelectInfoReply { Status = 1 };
        select10.Characters.Add(new CharacterSelectInfoReply.Character { Status = 1, CharacterId = 7, LastLogin = -0.5, LastServerId = 1, CharacterData = payload });

        var payload9 = new CharacterSelectInfoReply9.Character.CharacterPayload
        {
            Name = "Tester", Gender = Gender.Female, HeadId = 1, ModelId = 21, SkinTint = 5,
        };
        payload9.Customizations.Add((1, 2, 3));
        payload9.CharacterAttachments.Add(new CharacterSelectInfoReply9.Character.CharacterPayload.CharacterAttachment
        {
            ModelName = "Char_Biped_HumanFemale_Entities_Colony_000_Chest.adr", Slot = AttachmentSlot.Chest,
        });
        var select9 = new CharacterSelectInfoReply9 { Status = 1 };
        select9.Characters.Add(new CharacterSelectInfoReply9.Character { Status = 1, CharacterId = 7, LastLogin = 0, LastServerId = 1, CharacterData = payload9 });

        var zone = new ZoneServer(new ZoneServerModel { Id = 1, NameId = 62147, Host = "127.0.0.1", Port = 19000, Flags = 1 });
        var serverList = new ServerListReply();
        serverList.Servers.Add(zone.Build());

        var unknown7Type = typeof(ArtData).Assembly.GetType("LandmarkEmulator.AuthServer.Network.Message.Model.TunnelData.Unknown7");
        var unknown7 = (ITunnelData)Activator.CreateInstance(unknown7Type, true);
        unknown7Type.GetProperty("String").SetValue(unknown7, "Welcome to Landmark RE:Build! We're happy to have you!");

        var auth = new Dictionary<string, string>
        {
            ["login_reply"] = Hex(Auth(AuthMessageOpcode.LoginReply, new LoginReply { LoggedIn = true, Status = 1 })),
            ["login_reply_9"] = Hex(Auth(AuthMessageOpcode.LoginReply, new LoginReply_9 { LoggedIn = false, Status = 0 })),
            ["select_10"] = Hex(Auth(AuthMessageOpcode.CharacterSelectInfoReply, select10)),
            ["select_9"] = Hex(Auth(AuthMessageOpcode.CharacterSelectInfoReply, select9)),
            ["select_empty"] = Hex(Auth(AuthMessageOpcode.CharacterSelectInfoReply, new CharacterSelectInfoReply { Status = 1 })),
            ["server_list"] = Hex(Auth(AuthMessageOpcode.ServerListReply, serverList)),
            ["create_reply"] = Hex(Auth(AuthMessageOpcode.CharacterCreateReply, new CharacterCreateReply { Result = CharacterCreateResult.Success, CharacterId = 42 })),
            ["delete_reply"] = Hex(Auth(AuthMessageOpcode.CharacterDeleteReply, new CharacterDeleteReply { CharacterId = 42, Status = 1 })),
            ["force_disconnect"] = Hex(Auth(AuthMessageOpcode.ForceDisconnect, new LandmarkEmulator.AuthServer.Network.Message.Model.ForceDisconnect { Reason = 3 })),
            ["login_reply_character"] = Hex(Auth(AuthMessageOpcode.CharacterLoginReply, new CharacterLoginReply
            {
                CharacterId = 7, ServerId = 1, Result = CharacterLoginResult.Success,
                Server = new CharacterLoginReply.ServerInfo
                {
                    ServerAddress = "127.0.0.1:19000", AccountName = "user", EncryptionKey = key, CharacterId = 7,
                    CharacterName = "Tester", Guid = 1, ServerTicket = "00112233445566778899AABBCCDDEEFF",
                },
            })),
            ["login_reply_character_fail"] = Hex(Auth(AuthMessageOpcode.CharacterLoginReply, new CharacterLoginReply { CharacterId = 7, ServerId = 9, Result = CharacterLoginResult.ServerNotFound })),
            ["tunnel_name_validation"] = Hex(Auth(AuthMessageOpcode.TunnelPacketServerToClient, new TunnelPacketServerToClient
            {
                Type = TunnelDataType.NameValidationReply,
                Data = new NameValidationReply { Result = NameValidationResult.NameTaken, FirstName = "Bob" },
            })),
            ["tunnel_unknown7"] = Hex(Auth(AuthMessageOpcode.TunnelPacketServerToClient, new TunnelPacketServerToClient { Type = TunnelDataType.Unknown7, Data = unknown7 })),
            ["tunnel_claims"] = Hex(Auth(AuthMessageOpcode.TunnelPacketServerToClient, new TunnelPacketServerToClient { Type = TunnelDataType.ClaimData, Data = new ClaimData() })),
        };
        var artData = JsonConvert.DeserializeObject<ArtData>(File.ReadAllText(Path.Combine(resources, "ArtTints.json")));
        var artPacket = Auth(AuthMessageOpcode.TunnelPacketServerToClient, new TunnelPacketServerToClient { ServerId = 0, Type = TunnelDataType.ArtData, Data = artData });
        auth["art_data_sha256"] = Sha(artPacket);
        auth["art_data_length"] = artPacket.Length.ToString();
        auth["art_data_head"] = Hex(artPacket.Take(256).ToArray());
        g["auth"] = auth;

        // ---------------- zone ----------------
        var getOpcodeBytes = typeof(WorldSession).GetMethod("GetOpcodeBytes", BindingFlags.NonPublic | BindingFlags.Instance);
        var session = RuntimeHelpers.GetUninitializedObject(typeof(WorldSession));
        var opcodeBytes = new Dictionary<string, string>();
        foreach (ZoneMessageOpcode op in Enum.GetValues(typeof(ZoneMessageOpcode)))
            opcodeBytes[((uint)op).ToString()] = Hex((byte[])getOpcodeBytes.Invoke(session, new object[] { (ZoneMessageOpcode?)op }));
        g["zone_opcode_bytes"] = opcodeBytes;

        var opcodeParse = new Dictionary<string, object>();
        foreach (var h in new[] { "2E00AABB", "26000100FF", "BC000100", "011500", "FFFF", "0F00", "1500010199", "00", "2F000300" })
        {
            var (op, offset) = WorldSession.GetOpcode(Convert.FromHexString(h));
            opcodeParse[h] = new { opcode = op.HasValue ? (long)(uint)op.Value : -1, offset };
        }
        g["zone_opcode_parse"] = opcodeParse;

        var sendSelfDump = File.ReadAllBytes(Path.Combine(resources, "SendSelf.bin"));
        var parsed = new SendSelfToClient();
        parsed.Read(new GamePacketReader(sendSelfDump.AsSpan().Slice(2).ToArray()));
        var rewritten = new ZonePacket(ZoneMessageOpcode.SendSelfToClient, parsed, true).Data;

        var built = new SendSelfToClient();
        built.Guid = 1;
        built.CharacterId = 7;
        built.AccountName = "user";
        built.GenderMaybe = Gender.Female;
        built.Unknown22 = 1;
        built.ModelId = 392;
        built.Model = new CharacterModelInfo { SkinId = 5, Race = 1, Gender = 2 };
        built.Model.Customisations.Add((1, 2, 3));
        built.Identity.FirstName = "Tester";
        built.Profiles.Add(new SendSelfToClient.Profile
        {
            Unknown0 = 46, NameId = new LandmarkText(571666), Unknown3 = 3, Unknown15 = true,
            Unknown19 = 2.8f, Unknown20 = 2.75f, Unknown21 = 0.4f, Unknown22 = 1, Unknown23 = 1.4f, Unknown24 = 15f,
            Unknown29 = 3, Unknown30 = 3, Unknown31 = 3,
        });
        built.CurrentProfile = 46;
        built.Unknown24.Add((46, 46, 0));
        built.Unknown30.Add((3, 46));
        built.Loadouts[0].Unknown1.Unknown1 = 46;
        var builtBytes = new ZonePacket(ZoneMessageOpcode.SendSelfToClient, built, true).Data;

        g["zone"] = new Dictionary<string, object>
        {
            ["send_self_roundtrip_sha256"] = Sha(rewritten),
            ["send_self_roundtrip_length"] = rewritten.Length,
            ["send_self_roundtrip_head"] = Hex(rewritten.Take(4096).ToArray()),
            ["send_self_built"] = Hex(builtBytes),
            ["game_time_sync"] = Hex(Game(new GameTimeSync { Time = 12345.678 - 0.003, CycleSpeed = 9.1f, Unknown0 = false })),
            ["synchronization"] = Hex(Game(new Synchronization { Time1 = 1.5, Time2 = 2.5, ClientTime = 1000.25, ServerTime = 500.125, ServerTime2 = 500.125, Time3 = 1000.25 })),
            ["zone_population"] = Hex(Game(new ClientUpdateZonePopulation())),
            ["preload_done"] = Hex(Game(new ClientUpdateDoneSendingPreloadCharacters())),
            ["init_params"] = Hex(Game(new InitializationParameters { Environment = "live" })),
        };

        File.WriteAllText(outFile, JsonConvert.SerializeObject(g, Formatting.Indented));
        Console.WriteLine($"Wrote {outFile}");
    }
}
