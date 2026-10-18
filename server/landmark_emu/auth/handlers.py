"""Auth server packet handlers (login, server list, character select/create/delete/login)."""

from __future__ import annotations

import base64
import logging
import random
from datetime import datetime

from ..shared.database.manager import database_manager
from ..shared.database.models import CharacterCustomisationModel, CharacterModel
from ..shared.events import TaskEvent, TaskGenericEvent
from ..shared.game.entity import AttachmentSlot, Gender, Race, enum_text
from ..shared.game.game_table import game_table_manager
from ..shared.network.crypto import get_random_bytes, to_hex_string
from ..shared.network.protocol import ProtocolVersion
from . import config
from .assets import auth_asset_manager
from .message_manager import AuthMessageOpcode, auth_handler
from .messages import (
    CharacterAttachment,
    CharacterAttachment9,
    CharacterCreateReply,
    CharacterCreateRequest,
    CharacterCreateRequest9,
    CharacterCreateResult,
    CharacterDeleteReply,
    CharacterDeleteRequest,
    CharacterLoginReply,
    CharacterLoginRequest,
    CharacterLoginResult,
    CharacterPayload,
    CharacterPayload9,
    CharacterSelectInfoReply,
    CharacterSelectInfoReply9,
    CharacterSelectInfoRequest,
    LoginReply,
    LoginReply9,
    LoginRequest,
    SelectCharacter,
    SelectCharacter9,
    ServerInfo,
    ServerListReply,
    ServerListRequest,
    TunnelPacketClientToServer,
    TunnelPacketServerToClient,
)
from .session import AuthSession
from .tunnel_data import (
    ClaimData,
    LoginInit,
    NameValidationReply,
    NameValidationRequest,
    NameValidationResult,
    TunnelDataType,
    Unknown7,
)
from .utilities import validate_name
from .zone import zone_server_manager

log = logging.getLogger("LoginHandler")

# TODO (from the original): remove the random chest piece; it only keeps character select interesting.
RANDOM_CHEST_PIECES = (
    "Colony_000",
    "Trailblazer_000",
    "Founder_000",
    "Townsperson_000",
    "Dapper_000",
    "Adventurer_000",
    "Victorian_000",
    "Wanderer_000",
    "Qeynos_000_Heavy",
    "Colony_000_Heavy",
)

WELCOME_MESSAGE = "Welcome to Landmark RE:Build! We're happy to have you!"


def _days_since(moment: datetime | None) -> float:
    now = datetime.now()
    return (now - (moment or now)).total_seconds() / 86400.0 * -1.0


def _strict_names() -> bool:
    return config.current().creation_rules.strict_name


# --- Login ---------------------------------------------------------------------------------


@auth_handler(AuthMessageOpcode.LoginRequest, ProtocolVersion.LoginUdp_9)
def handle_login_request9(session: AuthSession, request: LoginRequest) -> None:
    # Hold outgoing packets until the asynchronous account lookup completes.
    session.toggle_packet_processing(False)

    def on_account(account):
        logged_in = account is not None
        session.enqueue_message(LoginReply9(logged_in=logged_in, status=int(logged_in)))
        session.initialise(account)
        session.toggle_packet_processing(True)

    session.events.append(
        TaskGenericEvent(
            database_manager.run(database_manager.auth_database.get_account_by_session_key, request.session_id),
            on_account,
        )
    )


@auth_handler(AuthMessageOpcode.LoginRequest, ProtocolVersion.LoginUdp_10)
def handle_login_request(session: AuthSession, request: LoginRequest) -> None:
    session.toggle_packet_processing(False)

    def on_account(account):
        logged_in = account is not None
        session.enqueue_message(
            TunnelPacketServerToClient(server_id=0, type=TunnelDataType.ArtData, data=auth_asset_manager.art_data)
        )
        session.enqueue_message(LoginReply(logged_in=logged_in, status=int(logged_in)))
        session.initialise(account)
        session.toggle_packet_processing(True)

    session.events.append(
        TaskGenericEvent(
            database_manager.run(database_manager.auth_database.get_account_by_session_key, request.session_id),
            on_account,
        )
    )


@auth_handler(AuthMessageOpcode.ServerListRequest)
def handle_server_list_request(session: AuthSession, request: ServerListRequest) -> None:
    reply = ServerListReply()
    for zone_server in zone_server_manager.zone_servers:
        reply.servers.append(zone_server.build())
    session.enqueue_message(reply)


# --- Character select ----------------------------------------------------------------------


def _model_for_gender(profile_id: int, gender: int) -> int:
    profile = game_table_manager.profile_definitions.get_entry(profile_id)
    if gender == Gender.Male:
        return profile.male_model_id
    if gender == Gender.Female:
        return profile.female_model_id
    return 252


@auth_handler(AuthMessageOpcode.CharacterSelectInfoRequest, ProtocolVersion.LoginUdp_10)
def handle_character_select_info_request(session: AuthSession, request: CharacterSelectInfoRequest) -> None:
    def on_characters(characters: list[CharacterModel]):
        session.characters.clear()
        session.characters.extend(characters)

        reply = CharacterSelectInfoReply(status=1)
        for model in characters:
            if model.delete_time is not None:
                continue

            payload = CharacterPayload(
                name=model.name,
                race=model.race,
                gender=model.gender,
                profile_id=model.profile_type_id,
                model_id=_model_for_gender(model.profile_type_id, model.gender),
            )
            payload.model.skin_id = model.skin_tint
            payload.model.race = model.race
            payload.model.gender = model.gender
            for custom in model.customisation:
                payload.model.customisations.append((custom.slot, custom.option, custom.tint))

            # Should only ever be a chest item in character select.
            payload.character_attachments.append(
                CharacterAttachment(
                    model_name=f"Char_Biped_[RACE][GENDER]_Entities_{random.choice(RANDOM_CHEST_PIECES)}_Chest.adr",
                    slot=AttachmentSlot.Head,
                )
            )

            reply.characters.append(
                SelectCharacter(
                    status=1,
                    character_id=model.id,
                    last_login=_days_since(model.last_online),
                    last_server_id=model.last_server_id,
                    character_data=payload,
                )
            )

        session.enqueue_message(reply)

    session.events.append(
        TaskGenericEvent(
            database_manager.run(database_manager.character_database.get_characters, session.account.id),
            on_characters,
        )
    )


@auth_handler(AuthMessageOpcode.CharacterSelectInfoRequest, ProtocolVersion.LoginUdp_9)
def handle_character_select_info_request9(session: AuthSession, request: CharacterSelectInfoRequest) -> None:
    def model_id(gender: int) -> int:
        return 23 if gender == Gender.Male else 21

    def on_characters(characters: list[CharacterModel]):
        session.characters.clear()
        session.characters.extend(characters)

        reply = CharacterSelectInfoReply9(status=1)
        for model in characters:
            if model.delete_time is not None:
                continue

            payload = CharacterPayload9(
                name=model.name,
                gender=model.gender,
                head_id=1,
                model_id=model_id(model.gender),
                skin_tint=model.skin_tint,
            )
            for custom in model.customisation:
                payload.customizations.append((custom.slot, custom.option, custom.tint))

            race = enum_text(Race, model.race)
            gender = enum_text(Gender, model.gender)
            payload.character_attachments.append(
                CharacterAttachment9(
                    model_name=f"Char_Biped_{race}{gender}_Entities_{random.choice(RANDOM_CHEST_PIECES)}_Chest.adr",
                    slot=AttachmentSlot.Chest,
                )
            )

            reply.characters.append(
                SelectCharacter9(
                    status=1,
                    character_id=model.id,
                    last_login=_days_since(model.last_online),
                    last_server_id=model.last_server_id,
                    character_data=payload,
                )
            )

        session.enqueue_message(reply)

    session.events.append(
        TaskGenericEvent(
            database_manager.run(database_manager.character_database.get_characters, session.account.id),
            on_characters,
        )
    )


# --- Tunnel --------------------------------------------------------------------------------


@auth_handler(AuthMessageOpcode.TunnelPacketClientToServer)
def handle_tunnel_packet_client_to_server(session: AuthSession, packet: TunnelPacketClientToServer) -> None:
    data = packet.data
    if isinstance(data, NameValidationRequest):
        # Nothing is created at this point, so just answer with the validation result.
        first_name = data.first_name

        def on_result(result: NameValidationResult):
            session.enqueue_message(
                TunnelPacketServerToClient(
                    type=TunnelDataType.NameValidationReply,
                    data=NameValidationReply(result=result, first_name=first_name),
                )
            )

        session.events.append(
            TaskGenericEvent(database_manager.run(validate_name, first_name, _strict_names()), on_result)
        )
    elif isinstance(data, LoginInit):
        session.enqueue_message(
            TunnelPacketServerToClient(server_id=0, type=TunnelDataType.Unknown7, data=Unknown7(string=WELCOME_MESSAGE))
        )
        session.enqueue_message(TunnelPacketServerToClient(server_id=0, type=TunnelDataType.ClaimData, data=ClaimData()))
    else:
        log.warning("Unknown Tunnel Data")


# --- Character create ----------------------------------------------------------------------


def _create_character(session: AuthSession, name: str, character: CharacterModel) -> None:
    """Validate the name, then save the character and reply (both off the event loop)."""

    def on_validated(result: NameValidationResult):
        if result != NameValidationResult.Success:
            session.enqueue_message(CharacterCreateReply(result=CharacterCreateResult.UnableToCreate))
            return

        character.id = auth_asset_manager.next_character_id()
        character.account_id = session.account.id

        def on_saved():
            session.characters.append(character)
            session.enqueue_message(
                CharacterCreateReply(result=CharacterCreateResult.Success, character_id=character.id)
            )

        session.events.append(
            TaskEvent(database_manager.run(database_manager.character_database.create_character, character), on_saved)
        )

    session.events.append(TaskGenericEvent(database_manager.run(validate_name, name, _strict_names()), on_validated))


def _customisations(options: list[tuple[int, int, int]]) -> list[CharacterCustomisationModel]:
    return [CharacterCustomisationModel(slot=slot, option=option, tint=tint) for slot, option, tint in options]


@auth_handler(AuthMessageOpcode.CharacterCreateRequest, ProtocolVersion.LoginUdp_10)
def handle_character_create_request(session: AuthSession, request: CharacterCreateRequest) -> None:
    # TODO (from the original): add the starting outfit.
    character = CharacterModel(
        name=request.name,
        gender=request.gender & 0xFF,
        race=request.race & 0xFF,
        profile_type_id=request.profile_type_id,
        skin_tint=request.skin_tint,
        customisation=_customisations(request.customisation_options),
    )
    _create_character(session, request.name, character)


@auth_handler(AuthMessageOpcode.CharacterCreateRequest, ProtocolVersion.LoginUdp_9)
def handle_character_create_request9(session: AuthSession, request: CharacterCreateRequest9) -> None:
    character = CharacterModel(
        name=request.name,
        gender=request.gender & 0xFF,
        race=int(Race.Human),
        profile_type_id=request.profile_type_id,
        skin_tint=request.skin_tint,
        customisation=_customisations(request.customisation_options),
    )
    _create_character(session, request.name, character)


# --- Character delete ----------------------------------------------------------------------


@auth_handler(AuthMessageOpcode.CharacterDeleteRequest)
def handle_character_delete_request(session: AuthSession, request: CharacterDeleteRequest) -> None:
    character = next((c for c in session.characters if c.id == request.character_id), None)
    if character is None:
        session.enqueue_message(CharacterDeleteReply(character_id=request.character_id, status=0))
        return

    session.toggle_packet_processing(False)

    def on_deleted():
        session.toggle_packet_processing(True)
        # Send an empty CharacterSelectInfoReply first, otherwise the client bugs out.
        session.enqueue_message(CharacterSelectInfoReply(status=1))
        session.enqueue_message(CharacterDeleteReply(character_id=request.character_id, status=1))

    session.events.append(
        TaskEvent(
            database_manager.run(
                database_manager.character_database.soft_delete_character, character.id, character.name
            ),
            on_deleted,
        )
    )


# --- Character login -----------------------------------------------------------------------


def _single_or_none(items, predicate):
    matches = [item for item in items if predicate(item)]
    if len(matches) > 1:
        raise LookupError("Sequence contains more than one matching element")
    return matches[0] if matches else None


@auth_handler(AuthMessageOpcode.CharacterLoginRequest)
def handle_character_login_request(session: AuthSession, request: CharacterLoginRequest) -> None:
    result = CharacterLoginResult.Success
    server = _single_or_none(zone_server_manager.zone_servers, lambda s: s.id == request.server_id)
    if server is None:
        result = CharacterLoginResult.ServerNotFound

    # TODO (from the original): confirm the server is online and accepting players.

    character = _single_or_none(session.characters, lambda c: c.id == request.character_id)
    if character is None:
        result = CharacterLoginResult.NotAllowed

    if result != CharacterLoginResult.Success:
        session.enqueue_message(
            CharacterLoginReply(character_id=request.character_id, server_id=request.server_id, result=result)
        )
        return

    server_ticket = to_hex_string(get_random_bytes(16))

    def on_ticket_saved():
        server_info = ServerInfo(
            server_address=f"{server.host}:{server.port}",
            account_name=session.account.username,
            encryption_key=base64.b64decode(session.encryption_key),
            character_id=character.id,
            character_name=character.name,
            guid=1,  # TODO (from the original): have a central service or the zone server provide the GUID.
            server_ticket=server_ticket,
        )
        session.enqueue_message(
            CharacterLoginReply(
                character_id=request.character_id,
                server_id=request.server_id,
                result=result,
                server=server_info,
            )
        )

    session.events.append(
        TaskEvent(
            database_manager.run(database_manager.auth_database.update_server_ticket, session.account, server_ticket),
            on_ticket_saved,
        )
    )
