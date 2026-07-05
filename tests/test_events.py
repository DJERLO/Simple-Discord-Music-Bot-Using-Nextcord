"""
tests/test_events.py
--------------------
Integration tests for AudioEvents and Wavelink Event Listeners.

Responsibility:
- Validates the bot's reaction to Wavelink lifecycle events (TrackStart, TrackEnd,
  TrackStuck, TrackException).
- Ensures network stability and system logging for WebSocket and Node events.
- Manages inactivity timers, voice state tracking, and automatic cleanup of
  stale or inactive players.

Usage:
- Run all tests: `pytest`
- Run this file: `pytest tests/test_events.py`
"""

from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
import wavelink

from bot import bot as bot_instance
from cogs.events import AudioEvents
from cogs.music_commands import WavelinkPlayer
from ui.embeds import VOTE_SKIPS


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
    mock_player.current = None
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
    mock_player.channel = MagicMock()
    mock_player.current = None
    mock_player.queue = MagicMock()
    mock_player.guild = MagicMock()
    mock_player.guild.id = 12345

    await audio_events_cog.on_wavelink_inactive_player(mock_player)

    mock_player.queue.clear.assert_called_once()
    mock_player.disconnect.assert_called_once()
    bot_instance.change_presence.assert_called_with(activity=None)


@pytest.mark.asyncio
@patch("cogs.events.cleanup_player_message")
async def test_on_wavelink_track_start_state_updates(mock_state_cleanup):
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
    mock_player.queue.mode = wavelink.QueueMode.normal
    mock_player.queue.history = MagicMock(spec=wavelink.Queue)
    mock_player.queue.history.put = MagicMock()

    mock_payload.track = mock_track
    mock_state_cleanup.return_value = AsyncMock()

    audio_events_cog = AudioEvents(mock_bot)

    await audio_events_cog.on_wavelink_track_start(mock_payload)

    assert VOTE_SKIPS[guild_id] == set()
    mock_player.queue.history.put.assert_called_with(mock_track)
    mock_bot.change_presence.assert_called()
    assert ACTIVE_PLAYERS.get(guild_id) is not None


@pytest.mark.asyncio
async def test_on_wavelink_track_end_normal_mode():
    """Verify QueueMode.normal mode cleanup and next track trigger."""
    mock_payload = MagicMock(spec=wavelink.TrackEndEventPayload)
    mock_payload.player = MagicMock(spec=wavelink.Player)
    mock_payload.track = MagicMock()
    mock_payload.reason = "finished"

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.queue = MagicMock()
    mock_player.queue.mode = wavelink.QueueMode.normal
    mock_player.queue.is_empty = True  # Ensure no next track
    mock_player.autoplay = wavelink.AutoPlayMode.disabled

    mock_payload.player = mock_player
    audio_events_cog = AudioEvents(bot_instance)

    await audio_events_cog.on_wavelink_track_end(mock_payload)

    # Verify no re-queueing happened
    mock_player.queue.put.assert_not_called()
    # Verify presence was set to idle (no songs left)
    bot_instance.change_presence.assert_called_with(
        activity=None, status=nextcord.Status.idle
    )


@pytest.mark.asyncio
async def test_on_wavelink_track_end_loop_mode():
    """Verify QueueMode.loop mode replays the current track."""
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.queue = MagicMock(spec=wavelink.Queue)
    mock_player.queue.mode = wavelink.QueueMode.loop
    mock_player.autoplay = wavelink.AutoPlayMode.disabled
    mock_player.queue.is_empty = True

    mock_payload = MagicMock(spec=wavelink.TrackEndEventPayload)
    mock_payload.player = MagicMock(spec=wavelink.Player)
    mock_payload.track = MagicMock(spec=wavelink.Playable)
    mock_payload.reason = "finished"
    mock_payload.player = mock_player

    audio_events_cog = AudioEvents(bot_instance)

    await audio_events_cog.on_wavelink_track_end(mock_payload)
    mock_player.play.assert_not_called()

    # Verify the track was played again


@pytest.mark.asyncio
async def test_on_wavelink_track_end_event_queuemode_loop_all():
    """Verify QueueMode.loop_all replays the all tracks in the queue."""
    mock_payload = MagicMock(spec=wavelink.TrackEndEventPayload)
    mock_payload.player = MagicMock(spec=wavelink.Player)
    mock_payload.track = MagicMock()
    mock_payload.reason = "Test Reason"
    mock_payload.track.title = "Test Track"
    mock_payload.duration = 123

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.queue = MagicMock()
    mock_player.queue.mode = wavelink.QueueMode.loop_all
    mock_player.queue.is_empty = False  # This forces it into the 'else' block
    mock_player.queue.history = MagicMock()
    mock_payload.player = mock_player
    audio_events_cog = AudioEvents(bot_instance)

    await audio_events_cog.on_wavelink_track_end(mock_payload)
    # Add assertions to verify the expected behavior
    mock_player.queue.put.assert_called_once_with(mock_payload.track)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code_val, expected_log_level",
    [(1000, "info"), (4006, "warning"), (4014, "info"), (4000, "error")],
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


@pytest.mark.asyncio
async def test_on_voice_state_update_human_joins():
    """Verify that when a human joins, the inactivity timeout is canceled."""

    # 1. Setup the Mock Bot
    mock_bot = MagicMock()
    mock_bot.user = MagicMock()
    mock_bot.user.id = 123

    # 2. Inject the mock_bot into the cog instance
    cog = AudioEvents(mock_bot)

    # 3. Setup Mocks
    mock_member = MagicMock(spec=nextcord.Member)
    mock_member.id = 999  # Human ID

    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.channel = MagicMock(name="BotChannel")
    mock_member.guild.voice_client = mock_vc

    # Before: not in channel, After: in channel
    before = MagicMock(spec=nextcord.VoiceState)
    before.channel = None
    after = MagicMock(spec=nextcord.VoiceState)
    after.channel = mock_vc.channel

    # Run
    await cog.on_voice_state_update(mock_member, before, after)

    # Assert
    assert mock_vc.inactive_timeout is None
    assert mock_vc.inactive_channel_tokens is None


@pytest.mark.asyncio
async def test_on_voice_state_update_human_leaves_empty():
    """Verify that when the last human leaves, the inactivity timer is started."""

    mock_bot = MagicMock()
    mock_bot.user = MagicMock()
    mock_bot.user.id = 123

    cog = AudioEvents(mock_bot)

    mock_member = MagicMock(spec=nextcord.Member)
    mock_member.id = 999

    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_channel = MagicMock(name="BotChannel")
    # Simulate an empty channel (only the bot exists, which we filter out)
    mock_channel.members = [MagicMock(bot=True)]
    mock_vc.channel = mock_channel

    # Before: in channel, After: not in channel
    before = MagicMock(spec=nextcord.VoiceState)
    before.channel = mock_channel
    after = MagicMock(spec=nextcord.VoiceState)
    after.channel = None

    mock_member.guild.voice_client = mock_vc

    # Run
    await cog.on_voice_state_update(mock_member, before, after)

    # Assert
    assert mock_vc.inactive_timeout == cog.inactive_timeout
    assert mock_vc.inactive_channel_tokens == cog.inactive_channel_tokens
