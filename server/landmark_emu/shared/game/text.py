"""Localised text lookup (``en_us_data.dat``) and the Jenkins lookup2 hash it is keyed by."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("TextManager")

_M = 0xFFFFFFFF


def _mix(a: int, b: int, c: int) -> tuple[int, int, int]:
    a = (a - b - c) & _M; a ^= c >> 13
    b = (b - c - a) & _M; b ^= (a << 8) & _M
    c = (c - a - b) & _M; c ^= b >> 13
    a = (a - b - c) & _M; a ^= c >> 12
    b = (b - c - a) & _M; b ^= (a << 16) & _M
    c = (c - a - b) & _M; c ^= b >> 5
    a = (a - b - c) & _M; a ^= c >> 3
    b = (b - c - a) & _M; b ^= (a << 10) & _M
    c = (c - a - b) & _M; c ^= b >> 15
    return a, b, c


def jenkins_lookup2(value: str) -> int:
    """32-bit lookup2 hash by Bob Jenkins (public domain), over UTF-16 code units."""
    data = value.encode("utf-16-le")
    k = [data[i] | (data[i + 1] << 8) for i in range(0, len(data), 2)]
    length = len(k)
    if length == 0:
        return 0

    a = b = 0x9E3779B9
    c = 0
    p = 0
    remaining = length
    while remaining >= 12:
        a = (a + k[p] + (k[p + 1] << 8) + (k[p + 2] << 16) + (k[p + 3] << 24)) & _M
        b = (b + k[p + 4] + (k[p + 5] << 8) + (k[p + 6] << 16) + (k[p + 7] << 24)) & _M
        c = (c + k[p + 8] + (k[p + 9] << 8) + (k[p + 10] << 16) + (k[p + 11] << 24)) & _M
        a, b, c = _mix(a, b, c)
        p += 12
        remaining -= 12

    c = (c + length) & _M
    if remaining >= 11: c = (c + (k[p + 10] << 24)) & _M
    if remaining >= 10: c = (c + (k[p + 9] << 16)) & _M
    if remaining >= 9: c = (c + (k[p + 8] << 8)) & _M
    # The first byte of c is reserved for the length.
    if remaining >= 8: b = (b + (k[p + 7] << 24)) & _M
    if remaining >= 7: b = (b + (k[p + 6] << 16)) & _M
    if remaining >= 6: b = (b + (k[p + 5] << 8)) & _M
    if remaining >= 5: b = (b + k[p + 4]) & _M
    if remaining >= 4: a = (a + (k[p + 3] << 24)) & _M
    if remaining >= 3: a = (a + (k[p + 2] << 16)) & _M
    if remaining >= 2: a = (a + (k[p + 1] << 8)) & _M
    if remaining >= 1: a = (a + k[p]) & _M
    a, b, c = _mix(a, b, c)
    return c


_LEADING_DIGIT = re.compile(r"^\d+")


class TextManager:
    # The original pre-computes a reverse lookup for ids below this bound only.
    MAX_TEXT_ID = 1_000_000

    def __init__(self):
        self._hash_to_string: dict[int, str] = {}
        self._reverse: dict[int, int] | None = None
        self._text_cache: dict[int, str] = {}

    @property
    def entry_count(self) -> int:
        return len(self._hash_to_string)

    def initialise(self, game_data_path: str | Path) -> None:
        log.info("Loading TextTables...")
        started = time.perf_counter()
        file_path = Path(game_data_path) / "en_us_data.dat"
        try:
            self._load_data_file(file_path)
        except Exception:
            log.critical("Failed to load %s", file_path, exc_info=True)
            raise
        log.info(
            "Loaded TextTables with %d entries in %dms.",
            len(self._hash_to_string),
            (time.perf_counter() - started) * 1000,
        )
        self._reverse = None
        self._text_cache.clear()

    def clear(self) -> None:
        self._hash_to_string.clear()
        self._reverse = None
        self._text_cache.clear()

    def load_entries(self, entries: dict[int, str]) -> None:
        """Populate directly (tests and tooling)."""
        for key, text in entries.items():
            self._hash_to_string.setdefault(key, text)
        self._reverse = None
        self._text_cache.clear()

    def _load_data_file(self, file_path: Path) -> None:
        skipped = 0
        with file_path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.rstrip("\r\n")
                # TODO (from the original): handle string entries that span multiple lines.
                if not _LEADING_DIGIT.match(line):
                    continue
                pieces = line.split("\t")
                if len(pieces) < 3:
                    skipped += 1
                    continue
                try:
                    key = int(pieces[0])
                except ValueError:
                    skipped += 1
                    continue
                self._hash_to_string.setdefault(key, pieces[2])
        if skipped:
            log.warning("Skipped %d malformed line(s) in %s", skipped, file_path.name)

    @staticmethod
    def get_hash(value: int | str) -> int:
        """Text hash for a NAME_ID number or a global string identifier."""
        if isinstance(value, int):
            value = f"Global.Text.{value}"
        elif not value.startswith("Global.Text"):
            value = "Global.Text." + value
        return jenkins_lookup2(value)

    def get_id_for_hash(self, text_hash: int) -> int | None:
        if text_hash not in self._hash_to_string:
            return None
        if self._reverse is None:
            log.info("Building ReverseLookup...")
            reverse: dict[int, int] = {}
            for key in range(self.MAX_TEXT_ID):
                h = self.get_hash(key)
                if h in self._hash_to_string:
                    reverse.setdefault(h, key)
            self._reverse = reverse
        return self._reverse.get(text_hash)

    def get_text_for_id(self, text_id: int) -> str:
        """The string that matches the given NAME_ID ("" when unknown)."""
        text = self._text_cache.get(text_id)
        if text is None:
            in_range = 0 <= text_id < self.MAX_TEXT_ID
            text = self._hash_to_string.get(self.get_hash(text_id), "") if in_range else ""
            self._text_cache[text_id] = text
        return text


text_manager = TextManager()


@dataclass
class LandmarkText:
    """A localised string reference; serialised as its uint32 id."""

    id: int = 0
    text: str = ""

    @classmethod
    def from_id(cls, text_id: int) -> LandmarkText:
        return cls(text_id, text_manager.get_text_for_id(text_id))

    def read(self, reader) -> None:
        self.id = reader.read_uint()
        self.text = text_manager.get_text_for_id(self.id)

    def write(self, writer) -> None:
        writer.write_uint(self.id)
