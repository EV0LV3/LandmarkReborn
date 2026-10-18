from __future__ import annotations

import logging

from ..shared.command import write_markup
from ..shared.database.manager import database_manager
from ..shared.network.crypto import PasswordProvider

log = logging.getLogger("AuthCommandHandler")


class AuthCommandHandler:
    """Console commands. Currently only ``account create <username> <password>``."""

    def invoke(self, command: str) -> None:
        parameters = command.split(" ")
        if len(parameters) == 4 and parameters[0] == "account":
            if parameters[1] == "create":
                write_markup(self._handle_account_create(parameters[2], parameters[3]))
            else:
                write_markup('{=Red}Command formatting incorrect. Must be "account create username password".')
        else:
            write_markup(f"{{=Red}}Command {parameters[0]} not recognised.")

    @staticmethod
    def _handle_account_create(username: str, password: str) -> str:
        auth_database = database_manager.auth_database
        if auth_database.account_exists(username):
            return "{=Yellow}Username already exists. Please try another."

        salt, verifier = PasswordProvider.generate_salt_and_verifier(password)
        auth_database.create_account(username, salt, verifier)
        return f"{{=Green}}Account {username} successfully created!"
