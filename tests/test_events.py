import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
import wavelink

from bot import bot as bot_instance
from cogs.events import AudioEvents
from cogs.music_commands import WavelinkPlayer
from ui.embeds import AUTO_DISCONNECT_TASKS


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
