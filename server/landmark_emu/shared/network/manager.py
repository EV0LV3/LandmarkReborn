"""UDP listener and session table."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable
from typing import Generic, TypeVar

from ..config import NetworkConfig
from .session import Address, NetworkSession

log = logging.getLogger("NetworkManager")

T = TypeVar("T", bound=NetworkSession)


class _UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self, manager: NetworkManager):
        self._manager = manager

    def datagram_received(self, data: bytes, addr: Address) -> None:
        self._manager.on_message(addr, data)

    def error_received(self, exc: Exception) -> None:
        # Windows reports ICMP "port unreachable" for vanished clients here; it is harmless.
        log.debug("UDP socket error: %s", exc)


class NetworkManager(Generic[T]):
    def __init__(self, session_factory: Callable[[], T]):
        self._session_factory = session_factory
        self._sessions: dict[Address, T] = {}
        self._transport: asyncio.DatagramTransport | None = None

    @property
    def sessions(self) -> Iterable[T]:
        return self._sessions.values()

    async def initialise(self, config: NetworkConfig) -> None:
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _UdpProtocol(self), local_addr=(config.host, config.port)
        )
        sock_name = self._transport.get_extra_info("sockname")
        log.info("Listening for UDP on %s:%d", sock_name[0], sock_name[1])

    @property
    def local_port(self) -> int:
        return self._transport.get_extra_info("sockname")[1] if self._transport else 0

    def on_message(self, remote: Address, data: bytes) -> None:
        session = self._sessions.get(remote)
        try:
            if session is not None:
                session.on_data(data)
                return

            session = self._session_factory()
            session.on_accept(remote)
            self._sessions[session.endpoint] = session
            session.on_send = self.send_data
            session.toggle_packet_processing(True)
            session.on_data(data)
        except Exception:
            log.exception("Failed to process datagram from %s:%s", remote[0], remote[1])

    def get_session(self, predicate: Callable[[T], bool]) -> T | None:
        """The single session matching ``predicate``; raises if more than one matches."""
        matches = [s for s in self._sessions.values() if predicate(s)]
        if len(matches) > 1:
            raise LookupError("Sequence contains more than one matching element")
        return matches[0] if matches else None

    def shutdown(self) -> None:
        for session in list(self._sessions.values()):
            session.on_disconnect()
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def update(self, last_tick: float) -> None:
        pending_remove = []
        for session in list(self._sessions.values()):
            if session.disconnected or session.heartbeat.flatline:
                pending_remove.append(session)
            else:
                session.update(last_tick)

        for session in pending_remove:
            self._sessions.pop(session.endpoint, None)

    def send_data(self, endpoint: Address, data: bytes) -> None:
        if self._transport is not None:
            self._transport.sendto(data, endpoint)
