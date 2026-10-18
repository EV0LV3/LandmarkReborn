"""HTTP API used by the launcher: account creation and authentication.

Same contract as the original ASP.NET minimal API: parameters come from the query string,
responses are camelCase JSON.
"""

from __future__ import annotations

import logging
import ssl
from datetime import datetime
from urllib.parse import urlsplit

from aiohttp import web

from ..shared.database.auth_database import SESSION_KEY_LIFETIME
from ..shared.database.manager import DatabaseManager
from ..shared.network.crypto import PasswordProvider, get_random_bytes, to_hex_string
from .config import WebApiConfig

log = logging.getLogger("AuthWebAPI")

DATABASE_KEY = web.AppKey("database", DatabaseManager)


def _required_query(request: web.Request, name: str) -> str:
    value = request.query.get(name)
    if value is None:
        raise web.HTTPBadRequest(text=f'Required parameter "string {name}" was not provided from query string.')
    return value


async def _hello(request: web.Request) -> web.Response:
    return web.Response(text="Hello World!")


async def _create(request: web.Request) -> web.Response:
    """Creates an account; returns the username when successful."""
    username = _required_query(request, "username")
    password = _required_query(request, "password")
    database = request.app[DATABASE_KEY]
    auth_database = database.auth_database

    if await database.run(auth_database.account_exists, username):
        return web.json_response(
            {"username": None, "message": "Unable to create account. Username already exists."}, status=409
        )

    salt, verifier = await database.run(PasswordProvider.generate_salt_and_verifier, password)
    await database.run(auth_database.create_account, username, salt, verifier)
    return web.json_response({"username": username, "message": "Success."})


async def _authenticate(request: web.Request) -> web.Response:
    """Returns a session key for the launcher to pass to the game client."""
    username = _required_query(request, "username")
    password = _required_query(request, "password")
    database = request.app[DATABASE_KEY]
    auth_database = database.auth_database

    account = await database.run(auth_database.get_account_by_username, username)
    if account is None:
        return web.Response(status=403)

    if not await database.run(PasswordProvider.verify_password, account.salt, account.verifier, password):
        return web.Response(status=403)

    session_key = to_hex_string(get_random_bytes(16))
    await database.run(auth_database.update_account_session_key, account, session_key)

    expiration = datetime.now() + SESSION_KEY_LIFETIME
    return web.json_response(
        {"sessionKey": session_key, "sessionKeyExpiration": expiration.isoformat(), "message": "Success."}
    )


def create_app(database: DatabaseManager) -> web.Application:
    app = web.Application()
    app[DATABASE_KEY] = database
    app.router.add_get("/", _hello)
    app.router.add_post("/create", _create)
    app.router.add_post("/authenticate", _authenticate)
    return app


class AuthWebApi:
    def __init__(self, config: WebApiConfig, database: DatabaseManager):
        self._config = config
        self._database = database
        self._runner: web.AppRunner | None = None
        self.port: int | None = None

    async def start(self) -> None:
        if not self._config.enabled:
            return

        uri = urlsplit(self._config.base_uri or "http://0.0.0.0:5080")
        ssl_context = None
        if uri.scheme == "https":
            if not (self._config.certificate_file and self._config.certificate_key_file):
                log.error(
                    "WebApi BaseURI %s uses https but no CertificateFile/CertificateKeyFile is configured; "
                    "the web API was not started.",
                    self._config.base_uri,
                )
                return
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(self._config.certificate_file, self._config.certificate_key_file)

        host = uri.hostname or "0.0.0.0"
        port = uri.port if uri.port is not None else (443 if ssl_context else 80)

        self._runner = web.AppRunner(create_app(self._database), access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host, port, ssl_context=ssl_context)
        try:
            await site.start()
        except OSError as exc:
            # Commonly WinError 10013: Windows reserves some ports (see
            # "netsh interface ipv4 show excludedportrange protocol=tcp").
            log.error(
                "Could not start the web API on %s:%d (%s). Pick another port in WebApi:BaseURI; "
                "the game servers keep running without it.",
                host, port, exc,
            )
            await self._runner.cleanup()
            self._runner = None
            return
        addresses = self._runner.addresses
        self.port = addresses[0][1] if addresses else port
        log.info("Web API listening on %s://%s:%d", uri.scheme, host, self.port)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
