"""Zone packet handlers (MiscHandler in the original)."""

from __future__ import annotations

import logging

from ..shared.network.message import to_json
from . import packet_data
from .message_manager import zone_handler
from .messages import (
    AbilityCasterInfoRequest,
    AbilityDefaultInfoRequest,
    ClientFinishedLoading,
    ClientIsReady,
    ClientLog,
    ClientUpdateDoneSendingPreloadCharacters,
    ClientUpdateZonePopulation,
    GameTimeSync,
    PlayerUpdateSetPlayerBio,
    Synchronization,
    ZoneDoneSendingInitialData,
)
from .opcodes import ZoneMessageOpcode as Op
from .resources import empty_terrain_manifest, packet_dump
from .session import WorldSession

log = logging.getLogger("MiscHandler")

ABILITY_CASTER_INFO_REPLIES = {
    221: packet_data.ABILITY_CASTER_INFO_221,
    1098: packet_data.ABILITY_CASTER_INFO_1098,
    326: packet_data.ABILITY_CASTER_INFO_326,
    1122: packet_data.ABILITY_CASTER_INFO_1122,
}


@zone_handler(Op.ClientLog)
def handle_client_log(session: WorldSession, client_log: ClientLog) -> None:
    log.debug("%s", to_json(client_log))


@zone_handler(Op.GameTimeSync)
def handle_game_time_sync(session: WorldSession, game_time_sync: GameTimeSync) -> None:
    session.enqueue_message(GameTimeSync(time=game_time_sync.time - 0.003, cycle_speed=9.1, unknown0=False))


@zone_handler(Op.ClientIsReady)
def handle_client_is_ready(session: WorldSession, client_is_ready: ClientIsReady) -> None:
    if session.ready_sent:
        return
    session.ready_sent = True

    session.enqueue_raw(Op.QuickChatBase, packet_data.QUICK_CHAT_BASE)
    session.enqueue_message(ClientUpdateDoneSendingPreloadCharacters())
    session.enqueue_raw(Op.AchievementBase, packet_dump("71-AchievementBase")[2:])
    session.enqueue_raw(Op.AchievementBase, packet_data.ACHIEVEMENT_BASE_2)
    session.enqueue_raw(Op.ActivityManagerBase, packet_data.ACTIVITY_MANAGER_BASE)
    session.enqueue_raw(Op.PlayerUpdateEffectTagCompositeEffectsEnable, packet_data.EFFECT_TAG_COMPOSITE_EFFECTS_ENABLE)
    session.enqueue_raw(Op.ResourcesBase, packet_data.RESOURCES_BASE_1)
    session.enqueue_raw(Op.ResourcesBase, packet_data.RESOURCES_BASE_2)
    session.enqueue_raw(Op.LoadoutsBase, packet_data.LOADOUTS_BASE)
    session.enqueue_raw(Op.CommandBase, packet_data.COMMAND_BASE_EMOTE_LIST)
    session.enqueue_raw(Op.InventoryBase, packet_data.INVENTORY_BASE)

    session.enqueue_message(ZoneDoneSendingInitialData())
    # Zone details are sent a second time in captured logs.
    session.enqueue_raw(Op.SendZoneDetails, packet_data.ZONE_DETAILS)
    session.enqueue_message(ClientUpdateZonePopulation())

    session.enqueue_raw(Op.LoadWelcomeScreen, packet_data.LOAD_WELCOME_SCREEN)
    session.enqueue_raw(Op.ExperienceBase, packet_data.EXPERIENCE_BASE)
    session.enqueue_raw(Op.PropBase, packet_data.PROP_BASE_TINTS)
    session.enqueue_raw(Op.ZoneCoordinateInfo, packet_data.ZONE_COORDINATE_INFO)
    session.enqueue_raw(Op.EquipmentBase, packet_data.EQUIPMENT_BASE)
    session.enqueue_raw(Op.WorldDisplayInfo, packet_data.WORLD_DISPLAY_INFO)
    session.enqueue_raw(Op.ClientUpdateMovementVersion, packet_data.CLIENT_UPDATE_MOVEMENT_VERSION)
    session.enqueue_raw(Op.ClientSettings, packet_data.CLIENT_SETTINGS)

    # The captured manifest (174,598 modified cells from the 0.695 live servers) keeps 0.589
    # clients rebuilding terrain for minutes until their hang watchdog kills them, so they get an
    # empty one. They still need a manifest before they build any terrain.
    if session.client_build.startswith("0.589."):
        session.enqueue_raw(Op.TerrainCellModifiedCellManifest, empty_terrain_manifest())
    else:
        session.enqueue_raw(Op.TerrainCellModifiedCellManifest, session.terrain_manifest[4:])
    session.enqueue_raw(Op.AreaDefinitionSetDefinitions, packet_data.AREA_DEFINITION_SET_DEFINITIONS)
    session.enqueue_raw(Op.PropBase, packet_dump("145-PropBase")[2:])
    session.enqueue_raw(Op.ActivityBase, packet_data.ACTIVITY_BASE)


@zone_handler(Op.ClientFinishedLoading)
def handle_client_finished_loading(session: WorldSession, message: ClientFinishedLoading) -> None:
    pass


@zone_handler(Op.Synchronization)
def handle_synchronization(session: WorldSession, synchronization: Synchronization) -> None:
    if synchronization.unknown0:
        return

    sync = Synchronization(
        time1=synchronization.time1,
        time2=synchronization.time2,
        client_time=synchronization.client_time,
        server_time=synchronization.client_time / 2.0,
        server_time2=synchronization.client_time / 2.0,
        time3=synchronization.client_time,
    )
    session.enqueue_message(sync)
    log.info("%s", to_json(sync))


@zone_handler(Op.AbilityCasterInfoRequest)
def handle_ability_caster_info_request(session: WorldSession, request: AbilityCasterInfoRequest) -> None:
    log.info("%s", to_json(request))
    reply = ABILITY_CASTER_INFO_REPLIES.get(request.unknown0)
    if reply is not None:
        session.enqueue_raw(Op.AbilityCasterInfoReply, reply)


@zone_handler(Op.PlayerUpdateSetPlayerBio)
def handle_player_set_player_bio(session: WorldSession, message: PlayerUpdateSetPlayerBio) -> None:
    session.enqueue_raw(Op.PlayerUpdateSetPlayerBio, packet_data.PLAYER_BIO_REPLY)


@zone_handler(Op.AbilityDefaultInfoRequest)
def handle_ability_default_info_request(session: WorldSession, message: AbilityDefaultInfoRequest) -> None:
    session.enqueue_raw(Op.AbilityDefaultInfoReply, packet_data.ABILITY_DEFAULT_INFO_REPLY)
