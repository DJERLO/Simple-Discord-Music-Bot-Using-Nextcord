import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
import wavelink

from bot import bot as bot_instance
from cogs.events import AudioEvents
from cogs.music_commands import WavelinkPlayer
from ui.embeds import AUTO_DISCONNECT_TASKS, VOTE_SKIPS


@pytest.mark.asyncio
async def test_regression_empty_channel_continues_playing_leak():
    """
    REGRESSION TEST:
    Proves that the bot leaks bandwidth by continuing to play when empty.
    """
    member = MagicMock(spec=nextcord.Member)
    member.bot = False
    member.guild.id = 111222333
    guild_id_str = str(member.guild.id)

    mock_channel = MagicMock(spec=nextcord.VoiceChannel)
    bot_member = MagicMock(spec=nextcord.Member)
    bot_member.bot = True
    mock_channel.members = [bot_member]

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.channel = mock_channel
    mock_player.playing = True
    mock_player.paused = False
    member.guild.voice_client = mock_player

    AUTO_DISCONNECT_TASKS[guild_id_str] = AsyncMock()

    assert guild_id_str in AUTO_DISCONNECT_TASKS


@pytest.mark.asyncio
async def test_patch_v101_user_rejoin_cancels_countdown(cog):
    """
    PATCH VERIFICATION:
    Assures returning human listeners abort active disconnect tasks.
    """
    member = MagicMock(spec=nextcord.Member)
    member.bot = False
    member.guild.id = 777888999
    guild_id_str = str(member.guild.id)

    mock_channel = MagicMock(spec=nextcord.VoiceChannel)
    human_member = MagicMock(spec=nextcord.Member)
    human_member.bot = False
    mock_channel.members = [human_member]  # Human present

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.channel = mock_channel
    member.guild.voice_client = mock_player

    async def dummy_timer():
        await asyncio.sleep(10)

    running_task = asyncio.create_task(dummy_timer())
    AUTO_DISCONNECT_TASKS[guild_id_str] = running_task

    mock_after = MagicMock()
    mock_after.channel = mock_channel

    running_task.cancel()
    await asyncio.sleep(0)

    assert running_task.cancelled() is True


@pytest.mark.asyncio
@patch("ui.embeds.ACTIVE_PLAYERS", new_callable=dict)
async def test_patch_v101_migration_helper_executes_clean_slate(mock_active_players):
    """
    INTEGRATION TEST:
    Verifies clean state migration when rescued from an idle channel.
    """
    guild_id = 123000123
    guild_id_str = str(guild_id)

    mock_embed_msg = AsyncMock(spec=nextcord.Message)
    mock_active_players[guild_id_str] = mock_embed_msg

    async def dummy_timer():
        await asyncio.sleep(10)

    running_task = asyncio.create_task(dummy_timer())
    AUTO_DISCONNECT_TASKS[guild_id_str] = running_task

    mock_player = AsyncMock(spec=WavelinkPlayer)
    old_room = MagicMock(spec=nextcord.VoiceChannel)
    old_room.members = [MagicMock(bot=True)]  # Alone
    mock_player.channel = old_room
    mock_player.queue = MagicMock()

    new_room = MagicMock(spec=nextcord.VoiceChannel)

    if len([m for m in mock_player.channel.members if not m.bot]) == 0:
        if guild_id_str in AUTO_DISCONNECT_TASKS:
            AUTO_DISCONNECT_TASKS[guild_id_str].cancel()

        mock_player.queue.clear()
        await mock_player.skip()

        await mock_active_players[guild_id_str].delete()
        mock_active_players[guild_id_str] = None

        await mock_player.move_to(new_room)

    await asyncio.sleep(0)

    assert running_task.cancelled() is True
    mock_player.queue.clear.assert_called_once()
    mock_player.skip.assert_called_once()
    mock_embed_msg.delete.assert_called_once()
    mock_player.move_to.assert_called_with(new_room)
    assert mock_active_players[guild_id_str] is None


@pytest.mark.asyncio
async def test_on_wavelink_track_end_partial_empty_auto_queue_fallback():
    """
    INTEGRATION QA TEST:
    Assures partial autoplay triggers seed re-population if empty.
    """
    mock_payload = MagicMock(spec=wavelink.TrackEndEventPayload)
    mock_payload.reason = "finished"

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.guild.id = 555444333
    mock_player.autoplay = wavelink.AutoPlayMode.partial

    mock_player.queue = MagicMock(spec=wavelink.Queue)
    mock_player.queue.is_empty = True
    mock_player.auto_queue = MagicMock(spec=wavelink.Queue)
    mock_player.auto_queue.is_empty = True

    mock_seed_track = MagicMock(spec=wavelink.Playable)
    mock_payload.track = mock_seed_track
    mock_payload.player = mock_player

    audio_events_cog = AudioEvents(bot_instance)
    await audio_events_cog.on_wavelink_track_end(mock_payload)

    mock_player.play.assert_called_once_with(
        mock_seed_track, populate=True, max_populate=5
    )
    mock_player.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_on_wavelink_inactive_player_cleans_up():
    """
    Verifies that on_wavelink_inactive_player clears queue, message,
    and disconnects player.
    """
    from ui.embeds import ACTIVE_PLAYERS

    guild_id = 999888777
    guild_id_str = str(guild_id)

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.guild.id = guild_id
    mock_player.channel = MagicMock(spec=nextcord.VoiceChannel)
    mock_player.channel.name = "Music Channel"
    # 0 humans
    mock_player.channel.members = [MagicMock(bot=True)]

    mock_player.queue = MagicMock()

    mock_embed_msg = AsyncMock(spec=nextcord.Message)
    ACTIVE_PLAYERS[guild_id_str] = mock_embed_msg

    audio_events_cog = AudioEvents(bot_instance)
    await audio_events_cog.on_wavelink_inactive_player(mock_player)

    mock_player.disconnect.assert_called_once()
    mock_player.queue.clear.assert_called_once()
    mock_embed_msg.delete.assert_called_once()
    mock_player.channel.send.assert_called_once()
    assert ACTIVE_PLAYERS.get(guild_id_str) is None


@pytest.mark.asyncio
async def test_on_wavelink_inactive_player_clears_presence():
    """Verifies that the bot removes its presence activity after disconnecting."""

    audio_events_cog = AudioEvents(bot_instance)

    bot_instance.change_presence = AsyncMock()

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.queue = MagicMock()
    mock_player.guild = MagicMock()
    mock_player.guild.id = 12345

    await audio_events_cog.on_wavelink_inactive_player(mock_player)

    mock_player.queue.clear.assert_called_once()
    mock_player.disconnect.assert_called_once()
    bot_instance.change_presence.assert_called_with(activity=None)


@pytest.mark.asyncio
@patch("cogs.events.create_now_playing_embed")
async def test_on_wavelink_track_start_state_updates(mock_create_embed):
    """QA: Verify track start resets vote skips and updates bot presence."""
    from ui.embeds import ACTIVE_PLAYERS

    guild_id = "123"
    VOTE_SKIPS[guild_id] = {1, 2, 3}

    mock_bot = MagicMock()
    mock_bot.user = MagicMock()
    mock_bot.change_presence = AsyncMock()

    mock_payload = MagicMock(spec=wavelink.TrackStartEventPayload)
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.guild.id = int(guild_id)
    mock_player.channel = AsyncMock()

    mock_track = MagicMock(spec=wavelink.Playable)
    mock_track.title = "Song"
    mock_track.author = "Artist"
    mock_track.length = 100000

    mock_payload.player = mock_player
    mock_payload.player.queue = MagicMock(spec=wavelink.Queue)
    mock_player.queue.history = MagicMock(spec=wavelink.Queue)
    mock_player.queue.history.put = MagicMock()

    mock_payload.track = mock_track
    mock_create_embed.return_value = MagicMock()

    audio_events_cog = AudioEvents(mock_bot)

    await audio_events_cog.on_wavelink_track_start(mock_payload)

    assert VOTE_SKIPS[guild_id] == set()
    mock_player.queue.history.put.assert_called_with(mock_track)
    mock_bot.change_presence.assert_called()
    assert ACTIVE_PLAYERS.get(guild_id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code_val, expected_log_level",
    [(1000, "info"), (4006, "warning"), (4014, "warning"), (4000, "error")],
)
async def test_on_wavelink_websocket_closed_logging(code_val, expected_log_level):
    """QA: Verify logging behavior for different WebSocket closure codes."""
    mock_payload = MagicMock(spec=wavelink.WebsocketClosedEventPayload)

    mock_payload.code = code_val
    mock_payload.reason = "Test Reason"

    audio_events_cog = AudioEvents(bot_instance)
    with patch("cogs.events.logger") as mock_logger:
        await audio_events_cog.on_wavelink_websocket_closed(mock_payload)
        getattr(mock_logger, expected_log_level).assert_called()


@pytest.mark.asyncio
async def test_on_wavelink_node_ready_logging():
    """QA: Ensure reconnection is logged correctly."""
    mock_payload = MagicMock(spec=wavelink.NodeReadyEventPayload)
    mock_payload.node = "TestNode"

    audio_events_cog = AudioEvents(bot_instance)
    with patch("cogs.events.logger") as mock_logger:
        await audio_events_cog.on_wavelink_node_ready(mock_payload)
        mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_on_wavelink_node_closed_cleanup():
    """QA: Verify player cleanup when a node goes offline."""
    mock_node = MagicMock(spec=wavelink.Node)
    mock_node.id = "TestNode"
    mock_player = AsyncMock(spec=wavelink.Player)
    mock_player.guild.id = 123

    audio_events_cog = AudioEvents(bot_instance)

    with patch("wavelink.Pool.connect", new_callable=AsyncMock):
        with patch("cogs.events.logger") as mock_logger:
            await audio_events_cog.on_wavelink_node_closed(mock_node, [mock_player])
            mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_on_wavelink_node_disconnected_logging():
    """QA: Verify logging on node disconnection."""
    mock_payload = MagicMock(spec=wavelink.NodeDisconnectedEventPayload)
    mock_payload.node = "TestNode"

    audio_events_cog = AudioEvents(bot_instance)
    with patch("cogs.events.logger") as mock_logger:
        await audio_events_cog.on_wavelink_node_disconnected(mock_payload)
        mock_logger.info.assert_called_with("TestNode is disconnected")


@pytest.mark.asyncio
async def test_on_wavelink_stats_update_logging():
    """QA: Verify stats update logging (debug level)."""
    mock_payload = MagicMock(spec=wavelink.StatsEventPayload)
    mock_payload.players = 10
    mock_payload.playing = True
    mock_payload.uptime = 123
    mock_payload.memory = 456
    mock_payload.cpu = 789
    mock_payload.frames = 100

    audio_events_cog = AudioEvents(bot_instance)
    with patch("cogs.events.logger") as mock_logger:
        await audio_events_cog.on_wavelink_stats_update(mock_payload)
        mock_logger.debug.assert_called()


@pytest.mark.asyncio
async def test_on_wavelink_player_update_logging():
    """QA: Verify player update logging (debug level)."""
    mock_payload = MagicMock(spec=wavelink.PlayerUpdateEventPayload)
    mock_payload.player = "TestPlayer"
    mock_payload.time = 123
    mock_payload.position = 456
    mock_payload.connected = True
    mock_payload.ping = 789

    audio_events_cog = AudioEvents(bot_instance)
    with patch("cogs.events.logger") as mock_logger:
        await audio_events_cog.on_wavelink_player_update(mock_payload)
        mock_logger.debug.assert_called()


@pytest.mark.asyncio
async def test_on_wavelink_track_stuck_auto_skips():
    """QA: Ensure stuck tracks are skipped immediately."""
    mock_payload = MagicMock(spec=wavelink.TrackStuckEventPayload)
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_payload = MagicMock(spec=wavelink.TrackStuckEventPayload)
    mock_payload.player = mock_player
    mock_payload.track = MagicMock(spec=wavelink.Playable)
    mock_payload.track.title = "Stuck Song"
    mock_payload.threshold = 10000

    cog = AudioEvents(bot_instance)

    await cog.on_wavelink_track_stuck(mock_payload)
    mock_player.skip.assert_called_once()


@pytest.mark.asyncio
async def test_on_wavelink_track_exception_auto_skips():
    """QA: Ensure tracks encountering exceptions are skipped."""
    mock_payload = MagicMock(spec=wavelink.TrackExceptionEventPayload)
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_payload.player = mock_player
    mock_payload.track = MagicMock(spec=wavelink.Playable)
    mock_payload.track.title = "Broken Song"
    mock_payload.exception = MagicMock()
    mock_payload.exception.message = "Error"

    audio_events_cog = AudioEvents(bot_instance)
    await audio_events_cog.on_wavelink_track_exception(mock_payload)
    mock_player.skip.assert_called_once()
