"""Reliable data streams: sequencing, acknowledgement, fragmentation and RC4 for game data."""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from dataclasses import dataclass

from .crypto import Arc4Provider
from .packet_io import ProtocolPacketReader, ProtocolPacketWriter
from .protocol import DataFragment, DataWhole, read_length_prefixed_chunk

DEFAULT_ENCRYPTION_KEY = "F70IaxuU8C/w7FPXY1ibXw=="

MULTI_CHANNEL_PREFIX = b"\x00\x19"


class InvalidPacketValueException(Exception):
    """A packet contained data that cannot be valid; the session is dropped."""


class InvalidOperationError(Exception):
    pass


@dataclass(slots=True)
class DataPacket:
    data: bytes
    is_fragment: bool


class DataStreamBase:
    def __init__(self, encryption_key: str | None):
        self.last_ack: int | None = None
        self.next_sequence: int | None = None
        self.using_encryption = True
        self.rc4_key = base64.b64decode(encryption_key or DEFAULT_ENCRYPTION_KEY)
        self.data_packets: dict[int, DataPacket] = {}

    def set_encryption(self, using_encryption: bool) -> None:
        self.using_encryption = using_encryption


class DataStreamInput(DataStreamBase):
    """Reassembles, orders and decrypts incoming Data/DataFragment payloads.

    ``lenient_fragments`` enables the packet-capture parser behaviour: oversize fragment
    chains are clipped to the declared size and reassembly errors are logged, not raised.
    """

    def __init__(
        self,
        encryption_key: str | None,
        on_data: Callable[[bytes], None],
        on_out_of_order: Callable[[int], None] | None = None,
        on_ack: Callable[[int], None] | None = None,
        lenient_fragments: bool = False,
        name: str = "",
    ):
        super().__init__(encryption_key)
        self._on_data = on_data
        self._on_out_of_order = on_out_of_order
        self._on_ack = on_ack
        self._lenient = lenient_fragments
        self._prefix = f"{name}: " if name else ""
        self._last_processed_fragment = -1
        self._arc4 = Arc4Provider(self.rc4_key)
        self._log = logging.getLogger("DataStreamInput")

    def process_data_whole(self, data_whole: DataWhole) -> None:
        self._ready_data_for_processing(data_whole.sequence, data_whole.data, False)

    def process_data_fragment(self, data_fragment: DataFragment) -> None:
        self._ready_data_for_processing(data_fragment.sequence, data_fragment.data, True)

    def _ready_data_for_processing(self, sequence: int, data: bytes, is_fragment: bool) -> None:
        if self.next_sequence is None:
            self.next_sequence = sequence

        if sequence > self.next_sequence and self._on_out_of_order is not None:
            self._log.warning(
                "%sSequence out of order, expected %d but received %d", self._prefix, self.next_sequence, sequence
            )
            self._on_out_of_order(sequence)
            return

        last_ack = self.last_ack if self.last_ack is not None else -1
        ack = sequence
        for i in range(1, 0x10000):
            j = (last_ack + i) & 0xFFFF
            if j in self.data_packets:
                ack = j
            else:
                break

        if ack > last_ack:
            self.last_ack = ack
            if self._on_ack is not None:
                self._on_ack(ack)

        self.data_packets[sequence] = DataPacket(data, is_fragment)
        self.next_sequence = (self.last_ack + 1) & 0xFFFF

        self._parse_data_fragments()

    def _parse_data_fragments(self) -> None:
        next_fragment = (self._last_processed_fragment + 1) & 0xFFFF
        data_packet = self.data_packets.get(next_fragment)
        if data_packet is None:
            return

        if not data_packet.is_fragment:
            self._last_processed_fragment = next_fragment
            self._decrypt_data(self._parse_channel_data(data_packet.data))
            return

        if not self._lenient:
            self._reassemble(next_fragment, data_packet)
            return

        try:
            self._reassemble(next_fragment, data_packet)
        except Exception:
            self._log.exception("%sFailed to reassemble fragments", self._prefix)

    def _reassemble(self, next_fragment: int, data_packet: DataPacket) -> None:
        total_size = ProtocolPacketReader(data_packet.data).read_uint()
        data = bytearray(data_packet.data[4:])
        data_size = len(data)

        fragment_indices: list[int] = []
        finished: list[bytes] | None = None
        for i in range(1, 0x10000):
            j = (next_fragment + i) % 0xFFFF
            fragment = self.data_packets.get(j)
            if fragment is None:
                break

            fragment_indices.append(j)
            if self._lenient and data_size + len(fragment.data) > total_size:
                take = total_size - data_size
                data += fragment.data[:max(take, 0)]
                data_size += take
            else:
                data += fragment.data
                data_size += len(fragment.data)

            if data_size > total_size:
                raise InvalidPacketValueException("DataSize exceeds TotalSize. We've got a problem!")

            if data_size == total_size:
                for index in fragment_indices:
                    self.data_packets.pop(index, None)
                self._last_processed_fragment = j
                finished = self._parse_channel_data(bytes(data))
                break

        if finished is not None:
            self._decrypt_data(finished)

    @staticmethod
    def _parse_channel_data(data: bytes) -> list[bytes]:
        if len(data) >= 2 and data[0] == 0x00 and data[1] == 0x19:
            reader = ProtocolPacketReader(data[2:])
            pieces = []
            while reader.bytes_remaining != 0:
                pieces.append(read_length_prefixed_chunk(reader))
            return pieces
        return [data]

    def _decrypt_data(self, pieces: list[bytes]) -> None:
        for piece in pieces:
            parsed = bytearray(piece)
            if self.using_encryption:
                # Sometimes there is an extra 0x00 byte at the start that trips up the RC4.
                if len(piece) > 1 and piece[0] == 0 and piece[1] == 0:
                    parsed = bytearray(piece[1:])
                self._arc4.decrypt(parsed)
            self._on_data(bytes(parsed))

    def reset_encryption(self) -> None:
        self._arc4 = Arc4Provider(self.rc4_key)

    def set_encryption_key(self, key: str) -> None:
        self._arc4 = Arc4Provider(base64.b64decode(key))


class DataStreamOutput(DataStreamBase):
    """Encrypts, sequences and fragments outgoing game data and keeps it for resends."""

    def __init__(self, encryption_key: str | None, on_data: Callable[[int, DataPacket, bool], None]):
        super().__init__(encryption_key)
        self._on_data = on_data
        self._fragment_size = 0
        self._arc4 = Arc4Provider(self.rc4_key)

    @property
    def missing_acks(self) -> bool:
        return self.last_ack is not None and self.last_ack in self.data_packets

    def set_fragment_size(self, fragment_size: int) -> None:
        self._fragment_size = fragment_size

    def _advance_sequence(self) -> int:
        self.next_sequence = 0 if self.next_sequence is None else (self.next_sequence + 1) & 0xFFFF
        return self.next_sequence

    def pack_data(self, data: bytes) -> None:
        buffer = bytearray(data)
        if self.using_encryption:
            self._arc4.encrypt(buffer)

        if buffer and buffer[0] == 0:
            buffer[0:0] = b"\x00"

        if len(buffer) <= self._fragment_size:
            sequence = self._advance_sequence()
            packet = DataPacket(bytes(buffer), False)
            self.data_packets[sequence] = packet
            self._on_data(sequence, packet, False)
            return

        if self._fragment_size <= 0:
            raise InvalidOperationError("Fragment size has not been negotiated for this session.")

        writer = ProtocolPacketWriter()
        writer.write_uint(len(buffer))
        writer.write_bytes(buffer)
        combined = writer.to_bytes()
        for offset in range(0, len(combined), self._fragment_size):
            sequence = self._advance_sequence()
            packet = DataPacket(combined[offset:offset + self._fragment_size], True)
            self.data_packets[sequence] = packet
            self._on_data(sequence, packet, False)

    def handle_ack(self, sequence: int) -> None:
        if self.last_ack is None:
            self.last_ack = 0
        while self.last_ack < sequence:
            self.data_packets.pop(self.last_ack, None)
            self.last_ack += 1

    def resend_data(self, sequence: int) -> None:
        if self.last_ack is None:
            raise InvalidOperationError("Nullable object must have a value.")
        for i in range(self.last_ack, sequence + 1):
            packet = self.data_packets.get(i)
            if packet is None:
                raise InvalidOperationError("Cache error, could not resend data!")
            self._on_data(i, packet, True)

    def resend_data_on_ping(self) -> None:
        if self.last_ack is None:
            raise InvalidOperationError("Nullable object must have a value.")
        for i in range(self.last_ack, 0x10000):
            packet = self.data_packets.get(i)
            if packet is None:
                break
            self._on_data(i, packet, True)
