from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
import wavelink

from cogs.music_commands import WavelinkPlayer
from ui.views import QueueView


@pytest.mark.asyncio
async def test_queue_view_pagination_logic(songs, mock_user, guild_id, cog):
    """Tests that the QueueView correctly calculates pages and button states."""
    view = QueueView(songs, mock_user, guild_id, per_page=2)

    assert view.prev_page.disabled is True, (
        "Previous button should be disabled on page 1"
    )
    assert view.next_page.disabled is False, "Next button should be enabled on page 1"

    embed = view.get_embed()
    assert "Song Alpha" in embed.description
    assert "Song Beta" in embed.description
    assert "Song Gamma" not in embed.description
    assert embed.footer.text == "Total Songs: 3"


@pytest.mark.asyncio
async def test_clearqueue_command(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild.voice_client.queue.clear = MagicMock()
    interaction.guild.voice_client.auto_queue.clear = MagicMock()
    interaction.guild.voice_client.queue.is_empty = False
    interaction.guild.voice_client.auto_queue.is_empty = False

    await cog.clearqueue.callback(cog, interaction)

    interaction.guild.voice_client.queue.clear.assert_called_once()
    interaction.guild.voice_client.auto_queue.clear.assert_called_once()
    interaction.followup.send.assert_called_with(
        "The music queue has been cleared.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_shuffle_command_success(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    # Mocking the VC
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    interaction.guild.voice_client = mock_vc

    # Setup the state: User queue has items, auto_queue is empty for this specific test
    mock_vc.queue = MagicMock(spec=wavelink.Queue)
    mock_vc.queue.is_empty = False
    mock_vc.auto_queue = MagicMock(spec=wavelink.Queue)
    mock_vc.auto_queue.is_empty = True

    mock_vc.queue.shuffle = MagicMock()

    await cog.shuffle.callback(cog, interaction)

    mock_vc.queue.shuffle.assert_called_once()

    # Updated assertion for the new message
    interaction.followup.send.assert_called_with(
        "The queue has been shuffled.", ephemeral=True
    )


@pytest.mark.asyncio
@patch("cogs.music_commands.QueueSongList")
async def test_queue_command_enforces_recommendation_limit(mock_view_class, cog):
    """
    STRESS TEST:
    Confirms UI slices recommendations even if internal queue is flooded.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_msg = AsyncMock(spec=nextcord.Message)
    interaction.original_message = AsyncMock(return_value=mock_msg)

    interaction.guild_id = 123
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.autoplay = wavelink.AutoPlayMode.enabled
    mock_player.queue = []

    tracks = [MagicMock(spec=wavelink.Playable) for _ in range(20)]
    mock_player.auto_queue = tracks

    interaction.guild.voice_client = mock_player

    await cog.queue.callback(cog, interaction)

    args, _ = mock_view_class.call_args
    songs_list = args[0]

    # This will now pass once you implement the slice in music_commands.py
    assert len(songs_list) == 10


@pytest.mark.asyncio
async def test_remove_command_success(cog):
    """
    QA: Verify track removal from a specific
    regular queue position using 1-based indexing.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_track = MagicMock(spec=wavelink.Playable)
    mock_track.title = "Target Track"

    # Simulate a single track in the user queue
    mock_vc.queue = [mock_track]
    mock_vc.auto_queue = []
    interaction.guild.voice_client = mock_vc

    # With 1-based indexing, position=1 targets index 0
    await cog.remove.callback(cog, interaction, position=1)

    interaction.followup.send.assert_called_with(
        "🗑️ Removed track: **Target Track** from position `1` (Regular Queue).",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_remove_command_invalid_position(cog):
    """QA: Verify guard against out-of-bounds queue indices and empty states."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)

    # 1. Test completely empty queues guard
    mock_vc.queue = []
    mock_vc.auto_queue = []
    interaction.guild.voice_client = mock_vc

    await cog.remove.callback(cog, interaction, position=5)
    interaction.followup.send.assert_called_with(
        "The music queue is currently empty.", ephemeral=True
    )

    # 2. Test out-of-bounds position guard when tracks exist
    mock_track = MagicMock(spec=wavelink.Playable)
    mock_vc.queue = [mock_track]  # Total length = 1

    await cog.remove.callback(cog, interaction, position=3)
    interaction.followup.send.assert_called_with(
        "Invalid position. Please choose a track number between 1 and 1.",
        ephemeral=True,
    )


@pytest.mark.asyncio
@patch("cogs.music_commands.update_player_message", new_callable=AsyncMock)
async def test_remove_command_auto_queue_success(mock_update, cog):
    """QA: Verify track removal from the asynchronous auto-queue container structure."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)

    regular_track = MagicMock(spec=wavelink.Playable)
    regular_track.title = "Regular Track"
    regular_track.identifier = "abc"

    auto_track1 = MagicMock(spec=wavelink.Playable)
    auto_track1.title = "Autoplay Track 1"
    auto_track1.identifier = "xyz"

    auto_track2 = MagicMock(spec=wavelink.Playable)
    auto_track2.title = "Autoplay Track 2"
    auto_track2.identifier = "123"

    mock_vc.queue = [regular_track]

    mock_auto_queue = MagicMock()
    mock_auto_queue.__iter__ = MagicMock(return_value=iter([auto_track1, auto_track2]))
    mock_auto_queue.__len__ = MagicMock(return_value=2)
    mock_auto_queue.clear = MagicMock()
    mock_auto_queue.put = MagicMock()

    mock_vc.auto_queue = mock_auto_queue
    interaction.guild.voice_client = mock_vc

    # position=2 targets the first item in the auto-queue (index = 2 - 1 = 1)
    await cog.remove.callback(cog, interaction, position=2)

    # Confirm the track was safely removed and put back asynchronously
    mock_vc.auto_queue.clear.assert_called_once()
    mock_vc.auto_queue.put.assert_called_once_with(auto_track2)

    interaction.followup.send.assert_called_with(
        "🗑️ Removed track: "
        "**Autoplay Track 1** from position `2` (Auto-Queue (Autoplay)).",
        ephemeral=True,
    )
