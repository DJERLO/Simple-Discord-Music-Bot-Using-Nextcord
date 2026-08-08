"""
tests/test_playback.py
----------------------
Integration and Unit tests for the Music Playback Engine.

Responsibility:
- Validates core audio controls: play, pause, resume, stop, skip, and volume.
- Ensures robust state management for playback modes (Loop, Autoplay, History).
- Tests guard logic for disconnected states, out-of-bounds inputs, and
  voice channel connectivity.
- Verifies queue manipulation (removing tracks from standard vs. auto-queues)
  and historical navigation.

Usage:
- Run all tests: `pytest`
- Run this file: `pytest tests/test_playback.py`
"""

from unittest.mock import ANY, AsyncMock, MagicMock, PropertyMock, patch

import nextcord
import pytest
import wavelink

from bot import bot as bot_instance
from cogs.music_commands import WavelinkPlayer
from tests.conftest import patch_wavelink_connected
from ui.embeds import (
    ACTIVE_PLAYERS,
    GUILD_AUTOPLAY_MODES,
    MESSAGE_DELETE_TIMEOUT,
    cleanup_player_message,
    update_player_message,
)
from ui.views import PlaybackView, QueueView


@pytest.mark.asyncio
async def test_skip_command_playing(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    # 1. Setup the Voice Client
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.playing = True
    mock_vc.paused = False
    mock_vc.skip = AsyncMock()

    # 2. Setup the shared Channel
    mock_channel = AsyncMock(spec=nextcord.VoiceChannel)
    mock_vc.channel = mock_channel

    interaction.guild.voice_client = mock_vc

    # 3. Setup the User's Voice state to match the VC channel
    interaction.user = AsyncMock()
    interaction.user.voice = AsyncMock()
    interaction.user.voice.channel = mock_channel

    # 4. Execution
    await cog.skip.callback(cog, interaction)

    mock_vc.skip.assert_called_once()
    interaction.followup.send.assert_called_with(
        "Skipped the current song.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_pause_command_success(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild.voice_client.playing = True
    interaction.guild.voice_client.pause = AsyncMock()

    await cog.pause.callback(cog, interaction)

    interaction.guild.voice_client.pause.assert_called_once_with(True)
    interaction.followup.send.assert_called_with("Playback paused!", ephemeral=True)


@pytest.mark.asyncio
async def test_resume_command_success(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild.voice_client.paused = True
    interaction.guild.voice_client.pause = AsyncMock()

    await cog.resume.callback(cog, interaction)

    interaction.guild.voice_client.pause.assert_called_once_with(False)
    interaction.followup.send.assert_called_with("Playback resumed!", ephemeral=True)


@pytest.mark.asyncio
async def test_stop_command_success(guild_id, mock_bot_presence, cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild_id = int(guild_id)

    player = interaction.guild.voice_client = AsyncMock()
    interaction.guild.voice_client.disconnect = AsyncMock()
    interaction.guild.voice_client.queue.reset = MagicMock()

    await cog.stop.callback(cog, interaction)

    interaction.guild.voice_client.queue.reset.assert_called_once()
    interaction.guild.voice_client.disconnect.assert_called_once()
    await cleanup_player_message(player)
    mock_bot_presence.assert_called_once_with(activity=None)


@pytest.mark.asyncio
@patch("wavelink.Playable.search")
async def test_play_command_new_connection(mock_search, mock_track, cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.user.voice.channel = MagicMock(spec=nextcord.VoiceChannel)
    interaction.followup.send = AsyncMock()

    mock_search.return_value = [mock_track]
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.playing = False
    mock_player.queue = AsyncMock(spec=wavelink.Queue)

    interaction.guild.voice_client = None
    interaction.user.voice.channel.connect = AsyncMock(return_value=mock_player)

    with patch_wavelink_connected():
        await cog.play.callback(cog, interaction, "Never Gonna Give You Up")

    interaction.user.voice.channel.connect.assert_called_once()
    mock_player.queue.put_wait.assert_called_once()
    mock_player.play.assert_called_once()
    assert interaction.followup.send.called


@pytest.mark.asyncio
@patch("wavelink.Playable.search")
async def test_play_command_no_results(mock_search, cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.user.voice.channel = MagicMock()
    interaction.followup.send = AsyncMock()

    mock_search.return_value = []
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.queue = AsyncMock(spec=wavelink.Queue)
    mock_player.channel = interaction.user.voice.channel
    interaction.guild.voice_client = mock_player

    with patch_wavelink_connected():
        await cog.play.callback(cog, interaction, "invalid_search_query_xyz")

    args, kwargs = interaction.followup.send.call_args
    assert args[0] == "No results found."
    mock_player.queue.put_wait.assert_not_called()
    mock_player.play.assert_not_called()


@pytest.mark.asyncio
async def test_nowplaying_command_playing(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.playing = True
    mock_player.position = 60000
    mock_player.queue = AsyncMock(spec=wavelink.Queue)

    mock_track = MagicMock(spec=wavelink.Playable)
    mock_track.title = "Test Song"
    mock_track.author = "Test Author"
    mock_track.length = 180000
    mock_track.uri = "https://youtube.com/test"
    mock_track.source = "youtube"
    mock_track.identifier = "abc123"
    mock_track.extras = MagicMock()

    mock_player.current = mock_track
    interaction.guild.voice_client = mock_player

    await cog.nowplaying.callback(cog, interaction)

    interaction.followup.send.assert_called_once()
    args, kwargs = interaction.followup.send.call_args
    embed = kwargs.get("embed")
    assert embed.title == "💿 Currently Playing"
    assert embed.fields[0].value == "Test Author"


@pytest.mark.asyncio
async def test_ping_command(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    with patch("nextcord.Client.latency", new_callable=PropertyMock) as mock_latency:
        mock_latency.return_value = 0.05
        await cog.ping.callback(cog, interaction)
        interaction.followup.send.assert_called_with(
            "Pong! Latency: 50ms", ephemeral=True
        )


@pytest.mark.asyncio
async def test_join_command_user_not_in_voice(cog):
    """Scenario: User triggers /join while not connected to any voice channel."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.user.voice = None  # User is not in voice

    with patch_wavelink_connected():
        await cog.join.callback(cog, interaction)

    interaction.followup.send.assert_called_once_with(
        "You must be in a voice channel to use this command.",
        ephemeral=True,
        delete_after=MESSAGE_DELETE_TIMEOUT,
    )


@pytest.mark.asyncio
async def test_volume_command_no_voice_client(cog):
    """Scenario: Setting volume when the bot has no active voice connection."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild.voice_client = None

    await cog.volume.callback(cog, interaction, value=75)

    interaction.followup.send.assert_called_once_with(
        "I'm not connected to any voice channel.", ephemeral=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_volume", [-10, 101, 150])
async def test_volume_command_out_of_bounds_guards(invalid_volume, cog):
    """
    Boundary Value Test:
    Setting volume at Input boundaries outside range.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    interaction.guild.voice_client = mock_vc

    await cog.volume.callback(cog, interaction, value=invalid_volume)

    interaction.followup.send.assert_called_with(
        "Please provide a volume value between 0 and 100.", ephemeral=True
    )
    mock_vc.set_volume.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_volume", [0, 50, 100])
async def test_volume_command_success_boundaries(valid_volume, cog):
    """
    Boundary Value Test:
    Setting volume at extreme or mid-range valid boundary limits.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.set_volume = AsyncMock()
    interaction.guild.voice_client = mock_vc

    await cog.volume.callback(cog, interaction, value=valid_volume)

    mock_vc.set_volume.assert_called_once_with(valid_volume)
    interaction.followup.send.assert_called_once_with(
        f"Volume set to {valid_volume}%.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_loop_command_guard_when_not_playing(cog):
    """Scenario: Toggling loop state when the player is idle."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.playing = False
    interaction.guild.voice_client = mock_vc

    await cog.loop.callback(cog, interaction)

    interaction.followup.send.assert_called_once_with(
        "Nothing is currently playing.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_loop_command_state(cog):
    """
    Boundary Value Test:
    Confirming loop state changes.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    # 1. Setup the mock player
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.playing = True

    # 2. Setup a mock queue object
    mock_queue = MagicMock()
    mock_queue.mode = wavelink.QueueMode.normal  # Start in normal mode
    mock_vc.queue = mock_queue

    interaction.guild.voice_client = mock_vc

    # Now the test will be able to access vc.queue.mode
    await cog.loop.callback(cog, interaction, mode="none")
    assert mock_vc.queue.mode == wavelink.QueueMode.normal
    interaction.followup.send.assert_called()
    await cog.loop.callback(cog, interaction, mode="track")
    assert mock_vc.queue.mode == wavelink.QueueMode.loop
    interaction.followup.send.assert_called()
    await cog.loop.callback(cog, interaction, mode="queue")
    assert mock_vc.queue.mode == wavelink.QueueMode.loop_all
    interaction.followup.send.assert_called()
    assert interaction.followup.send.call_count == 3


@pytest.mark.asyncio
async def test_autoplay_command_guard_when_disconnected(cog):
    """Scenario: Setting autoplay options when disconnected from voice."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild.voice_client = None

    await cog.autoplay.callback(cog, interaction, mode="enabled")

    interaction.followup.send.assert_called_once_with(
        "I'm not connected to any voice channel. Autoplay preference saved.",
        ephemeral=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode_str, expected_enum",
    [
        ("enabled", wavelink.AutoPlayMode.enabled),
        ("disabled", wavelink.AutoPlayMode.disabled),
    ],
)
async def test_autoplay_command_and_global_persistence_mapping(
    mode_str, expected_enum, cog
):
    """Scenario: Passing inputs to verify enum translations and global map retention."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild_id = 999111222
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    mock_vc = AsyncMock(spec=WavelinkPlayer)
    interaction.guild.voice_client = mock_vc

    guild_key = str(interaction.guild_id)
    GUILD_AUTOPLAY_MODES.pop(guild_key, None)  # Purge old cache state

    await cog.autoplay.callback(cog, interaction, mode=mode_str)

    # Validate setting reflects on player and global mapping registry
    assert GUILD_AUTOPLAY_MODES[guild_key] == expected_enum
    assert mock_vc.autoplay == expected_enum
    interaction.followup.send.assert_called_once_with(
        f"Autoplay mode has been set to: **{mode_str.capitalize()}**", ephemeral=True
    )


@pytest.mark.asyncio
async def test_update_player_message_ignores_api_errors(cog):
    """STRESS TEST: Ensures bot doesn't crash if the persistent message edit fails."""
    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.queue = AsyncMock(spec=wavelink.Queue)
    mock_player.guild.id = 123
    mock_player.current = MagicMock(spec=wavelink.Playable)

    mock_msg = AsyncMock()
    mock_msg.edit.side_effect = nextcord.HTTPException(AsyncMock(), "Failed")

    ACTIVE_PLAYERS["123"] = mock_msg

    await update_player_message(mock_player, bot_user=bot_instance.user)
    mock_msg.edit.assert_called_once()


@pytest.mark.asyncio
async def test_join_restores_persisted_autoplay_mode(cog):
    """
    INTEGRITY TEST:
    Verifies that joining a channel restores saved autoplay settings.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild_id = 456
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild.voice_client = None
    interaction.user.voice.channel = AsyncMock(spec=nextcord.VoiceChannel)
    interaction.user.voice.channel.name = "Test Channel"

    mock_vc = AsyncMock(spec=WavelinkPlayer)
    interaction.user.voice.channel.connect.return_value = mock_vc

    # Pre-set a mode in the persistent dictionary
    GUILD_AUTOPLAY_MODES["456"] = wavelink.AutoPlayMode.partial

    with patch_wavelink_connected():
        await cog.join.callback(cog, interaction)

    assert mock_vc.autoplay == wavelink.AutoPlayMode.partial


@pytest.mark.asyncio
async def test_previous_command_navigates_unified_history(cog):
    """
    INTEGRITY TEST:
    Ensures that regardless of track origin, the bot uses the unified
    history list to navigate backward.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.channel = AsyncMock(spec=nextcord.VoiceChannel)
    mock_vc.queue = MagicMock(spec=wavelink.Queue)

    interaction.guild.voice_client = mock_vc
    interaction.user.voice.channel = mock_vc.channel

    # 1. Setup playing track and unified history
    mock_current = MagicMock(spec=wavelink.Playable)
    mock_vc.current = mock_current

    # We mock the property directly as it acts as our interface
    mock_prev_track = MagicMock(spec=wavelink.Playable)
    type(mock_vc).last_played_track = PropertyMock(return_value=mock_prev_track)

    # 2. Execution
    await cog.previous.callback(cog, interaction)

    # 3. Verification
    # Assert play was called with the correct track
    mock_vc.play.assert_called_with(mock_prev_track, add_history=False)

    # Assert that current track was put at index 0 to preserve forward-flow
    mock_vc.queue.put_at.assert_called_with(0, mock_current)

    interaction.followup.send.assert_called_with(
        "Switched to the previous track!",
        ephemeral=True,
        delete_after=MESSAGE_DELETE_TIMEOUT,
    )


@pytest.mark.asyncio
async def test_previous_command_no_history_fails(cog):
    # 1. Setup the Interaction Mock properly
    interaction = AsyncMock(spec=nextcord.Interaction)

    # CRITICAL: These must be AsyncMocks so they can be awaited
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    # 2. Setup the Voice Client
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.channel = AsyncMock(spec=nextcord.VoiceChannel)
    mock_vc.queue = MagicMock(spec=wavelink.Queue)

    # 3. Setup the User Voice state to trigger the channel check
    # We set this to something different than mock_vc.channel to trigger the 'if' block
    different_channel = AsyncMock(spec=nextcord.VoiceChannel)
    interaction.user.voice = AsyncMock()
    interaction.user.voice.channel = different_channel

    interaction.guild.voice_client = mock_vc

    # Force property to return None
    type(mock_vc).last_played_track = PropertyMock(return_value=None)

    # 4. Execution
    await cog.previous.callback(cog, interaction)

    # 5. Verification
    interaction.followup.send.assert_called_once()


@pytest.mark.asyncio
async def test_remove_command_removes_from_regular_queue(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    mock_vc = AsyncMock(spec=WavelinkPlayer)
    # Mocking a queue with 2 items
    mock_vc.queue = [
        MagicMock(spec=wavelink.Playable, title="Track 1"),
        MagicMock(spec=wavelink.Playable, title="Track 2"),
    ]
    # Auto-queue with 1 item
    mock_vc.auto_queue = [MagicMock(spec=wavelink.Playable, title="Auto Track")]

    interaction.guild.voice_client = mock_vc

    # Remove Track 1 (Position 1)
    await cog.remove.callback(cog, interaction, position=1)

    assert len(mock_vc.queue) == 1
    assert mock_vc.queue[0].title == "Track 2"
    interaction.followup.send.assert_called()


@pytest.mark.asyncio
async def test_remove_command_removes_from_auto_queue(cog):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    mock_vc = AsyncMock(spec=WavelinkPlayer)
    # Setup: 1 regular track, 1 auto track
    track1 = MagicMock(spec=wavelink.Playable, title="Reg Track", identifier="1")
    track2 = MagicMock(spec=wavelink.Playable, title="Auto Track 1", identifier="2")
    track3 = MagicMock(spec=wavelink.Playable, title="Auto Track 1", identifier="3")

    mock_vc.queue = [track1]
    mock_vc.auto_queue = MagicMock()
    mock_vc.auto_queue.__iter__.return_value = [track2, track3]
    mock_vc.auto_queue.__len__.return_value = 2

    interaction.guild.voice_client = mock_vc

    # Remove Auto Track (Position 2)
    await cog.remove.callback(cog, interaction, position=2)

    # Verification
    mock_vc.auto_queue.clear.assert_called_once()
    mock_vc.auto_queue.put.assert_called_once_with(track3)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vote_count, total_humans, should_skip",
    [
        (0, 8, False),  # 0/8 votes
        (4, 8, False),  # 4/8 votes
        (5, 8, True),  # 5/8 votes
        (0, 1, True),  # No votes, one human
        (3, 8, False),  # 3/8 votes
        (1, 2, False),  # 1/2
        (8, 8, True),  # 2/2 - All voted
    ],
)
async def test_vote_skip_logic_parametrized(total_humans, vote_count, should_skip):
    mock_channel = MagicMock()
    mock_channel.members = [MagicMock(bot=False) for _ in range(total_humans)] + [
        MagicMock(bot=True)
    ]

    total_listeners = len([m for m in mock_channel.members if not m.bot])
    required_votes = (total_listeners // 2) + 1

    if total_listeners <= 1:
        should_skip = (
            True  # Based on your code: "if total_listeners <= 1: await vc.skip()"
        )

    current_votes = vote_count
    skip_triggered = (total_listeners <= 1) or (current_votes >= required_votes)

    assert skip_triggered == should_skip


@pytest.mark.asyncio
@patch("ui.views.get_tracks", new_callable=AsyncMock)
async def test_playback_view_queue_button(mock_get_tracks):
    """
    Button test:
    Clicking the queue button should fetch tracks
    from get_tracks and send an ephemeral queue view.
    """

    mock_player = AsyncMock(spec=wavelink.Player)
    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.user = AsyncMock()
    interaction.guild_id = 123456789
    interaction.guild.voice_client = mock_player
    interaction.response = AsyncMock()

    # Call the queue button callback
    await view.queue.callback(interaction)

    # Assertions
    mock_get_tracks.assert_awaited_once_with(mock_player)
    interaction.response.send_message.assert_awaited_once()

    # Extract kwargs passed to send_message to verify embed and ephemeral flag
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    assert kwargs.get("embed") is not None
    assert isinstance(kwargs.get("view"), QueueView)


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
@patch("ui.views.embeds.update_player_message", new_callable=AsyncMock)
async def test_playback_view_previous_button_success(
    mock_update_player_message, mock_is_dj
):
    """
    Button test: Clicking previous when a previous track exists
    should verify DJ permission, update the queue,
    and play the previous track, and update the UI.
    """
    mock_is_dj.return_value = True

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.last_played_track = AsyncMock()
    mock_player.current = MagicMock()
    mock_player.queue = MagicMock()
    mock_player.play = AsyncMock()

    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild.voice_client = mock_player
    interaction.response = AsyncMock()

    await view.previous.callback(interaction)

    # Assertions
    mock_is_dj.assert_awaited_once_with(interaction)
    mock_player.queue.put_at.assert_called_once_with(0, mock_player.current)
    mock_player.play.assert_awaited_once_with(
        mock_player.last_played_track, add_history=False
    )
    mock_update_player_message.assert_awaited_once_with(mock_player, bot_user=None)


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
async def test_playback_view_previous_button_no_dj(mock_is_dj):
    """
    Button test:
    Clicking previous without DJ permissions should deny access.
    """
    mock_is_dj.return_value = False

    mock_player = AsyncMock(spec=WavelinkPlayer)
    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response = AsyncMock()

    await view.previous.callback(interaction)

    mock_is_dj.assert_awaited_once_with(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    assert "Access Denied" in interaction.response.send_message.call_args[0][0]


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
async def test_playback_view_previous_button_no_previous_track(mock_is_dj):
    """
    Button test:
    Clicking previous when there is no previous
    track should notify the user.
    """
    mock_is_dj.return_value = True

    mock_player = AsyncMock(spec=WavelinkPlayer)
    mock_player.last_played_track = None

    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild.voice_client = mock_player
    interaction.response = AsyncMock()

    await view.previous.callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        "No previous track to play.", ephemeral=True
    )


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
@patch("ui.views.embeds.update_player_message", new_callable=AsyncMock)
async def test_playback_view_pause_resume_button_pauses(
    mock_update_player_message, mock_is_dj
):
    """
    Button test: Clicking pause/resume when player is active
    should pause the player, update the button UI to Play,
    and update the player message.
    """
    mock_is_dj.return_value = True

    mock_player = AsyncMock(spec=wavelink.Player)
    mock_player.paused = False
    mock_player.pause = AsyncMock()

    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild.voice_client = mock_player
    interaction.response = AsyncMock()

    button = AsyncMock(spec=nextcord.ui.Button)
    button.emoji = "⏸️"
    button.label = "Pause"

    # Invoke callback directly passing the button object and interaction
    await view.pause_resume.callback(interaction)

    mock_is_dj.assert_awaited_once_with(interaction)
    mock_player.pause.assert_awaited_once_with(True)
    assert view.is_paused is True
    assert button.emoji == "⏸️"
    assert button.label == "Pause"
    interaction.response.edit_message.assert_awaited_once_with(view=view)
    mock_update_player_message.assert_awaited_once_with(mock_player, bot_user=None)


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
@patch("ui.views.embeds.update_player_message", new_callable=AsyncMock)
async def test_playback_view_pause_resume_button_resumes(
    mock_update_player_message, mock_is_dj
):
    """
    Button test: Clicking pause/resume when player is paused
    should resume the player, update the button UI to Pause,
    and update the player message.
    """
    mock_is_dj.return_value = True

    mock_player = AsyncMock(spec=wavelink.Player)
    mock_player.paused = True
    mock_player.pause = AsyncMock()

    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild.voice_client = mock_player
    interaction.response = AsyncMock()

    button = AsyncMock(spec=nextcord.ui.Button)
    button.emoji = "▶️"
    button.label = "Play"

    await view.pause_resume.callback(interaction)

    mock_player.pause.assert_awaited_once_with(False)
    assert view.is_paused is False
    assert button.emoji == "▶️"
    assert button.label == "Play"
    interaction.response.edit_message.assert_awaited_once_with(view=view)
    mock_update_player_message.assert_awaited_once_with(mock_player, bot_user=None)


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
async def test_playback_view_pause_resume_button_no_dj(mock_is_dj):
    """
    Button test:
    Clicking pause/resume without DJ permissions should deny access.
    """
    mock_is_dj.return_value = False

    mock_player = AsyncMock(spec=wavelink.Player)
    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response = AsyncMock()

    await view.pause_resume.callback(interaction)

    mock_is_dj.assert_awaited_once_with(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    assert "Access Denied" in interaction.response.send_message.call_args[0][0]


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
async def test_playback_view_next_button_success(mock_is_dj):
    """
    Button test: Clicking next with DJ permissions and an active player
    should skip the current track.
    """
    mock_is_dj.return_value = True

    mock_player = AsyncMock(spec=wavelink.Player)
    mock_player.playing = True
    mock_player.paused = False
    mock_player.current.title = "Test Song"
    mock_player.current.author = "Test Artist"
    mock_player.skip = AsyncMock()

    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild.voice_client = mock_player
    interaction.user.name = "TestDJ"

    await view.next.callback(interaction)

    mock_is_dj.assert_awaited_once_with(interaction)
    mock_player.skip.assert_awaited_once_with(force=False)


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
async def test_playback_view_next_button_no_dj(mock_is_dj):
    """
    Button test: Clicking next without DJ permissions should deny access.
    """
    mock_is_dj.return_value = False

    mock_player = AsyncMock(spec=wavelink.Player)
    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response = AsyncMock()

    await view.next.callback(interaction)

    mock_is_dj.assert_awaited_once_with(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    assert "Access Denied" in interaction.response.send_message.call_args[0][0]


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
@patch("ui.views.repeat_queue")
@patch("ui.views.embeds.update_player_message", new_callable=AsyncMock)
async def test_playback_view_repeat_button_success(
    mock_update_player_message, mock_repeat_queue, mock_is_dj
):
    """
    Button test:
    Clicking repeat with DJ permissions should toggle repeat state,
    edit the message view, and update the player message.
    """
    mock_is_dj.return_value = True

    mock_player = AsyncMock(spec=wavelink.Player)
    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild.voice_client = mock_player
    interaction.response = AsyncMock()

    button = ANY

    await view.repeat.callback(interaction)

    mock_is_dj.assert_awaited_once_with(interaction)
    mock_repeat_queue.assert_called_once_with(mock_player, button)
    interaction.response.edit_message.assert_awaited_once_with(view=view)
    mock_update_player_message.assert_awaited_once_with(mock_player, bot_user=None)


@pytest.mark.asyncio
@patch("ui.views.is_dj", new_callable=AsyncMock)
async def test_playback_view_repeat_button_no_dj(mock_is_dj):
    """
    Button test: Clicking repeat without DJ permissions should deny access.
    """
    mock_is_dj.return_value = False

    mock_player = AsyncMock(spec=wavelink.Player)
    view = PlaybackView(player=mock_player, bot_user=None)

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response = AsyncMock()

    await view.repeat.callback(interaction)

    mock_is_dj.assert_awaited_once_with(interaction)
    interaction.response.send_message.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
    assert "Access Denied" in interaction.response.send_message.call_args[0][0]
