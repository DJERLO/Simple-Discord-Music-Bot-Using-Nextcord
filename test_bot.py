import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import nextcord
import pytest
import wavelink

# Import the bot and view modules
import bot
from views import QueueView

# --- Fixtures ---


@pytest.fixture
def songs():
    return [
        ("https://link1.com", "Song Alpha", None, 125),
        ("https://link2.com", "Song Beta", None, 300),
        ("https://link3.com", "Song Gamma", None, 45),
    ]


@pytest.fixture
def mock_track():
    track = MagicMock(spec=wavelink.Playable)
    track.title = "Test Song"
    track.length = 180000  # 3 mins
    return track


@pytest.fixture
def mock_user():
    user = MagicMock(spec=nextcord.User)
    user.id = 12345
    user.display_name = "TestUser"
    user.avatar = None
    return user


@pytest.fixture
def guild_id():
    return "987654321"


@pytest.fixture(autouse=True)
def mock_bot_presence():
    with patch("bot.bot.change_presence", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture(autouse=True)
def clean_active_players():
    bot.ACTIVE_PLAYERS.clear()
    yield
    bot.ACTIVE_PLAYERS.clear()


# --- Tests ---


@pytest.mark.asyncio
async def test_queue_view_pagination_logic(songs, mock_user, guild_id):
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
async def test_skip_command_playing():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.playing = True
    interaction.guild.voice_client.paused = False
    interaction.guild.voice_client.skip = AsyncMock()

    await bot.skip.callback(interaction)

    interaction.guild.voice_client.skip.assert_called_once()
    interaction.response.send_message.assert_called_with(
        "Skipped the current song.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_pause_command_success():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.playing = True
    interaction.guild.voice_client.pause = AsyncMock()

    await bot.pause.callback(interaction)

    interaction.guild.voice_client.pause.assert_called_once_with(True)
    interaction.response.send_message.assert_called_with(
        "Playback paused!", ephemeral=True
    )


@pytest.mark.asyncio
async def test_resume_command_success():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.paused = True
    interaction.guild.voice_client.pause = AsyncMock()

    await bot.resume.callback(interaction)

    interaction.guild.voice_client.pause.assert_called_once_with(False)
    interaction.response.send_message.assert_called_with(
        "Playback resumed!", ephemeral=True
    )


@pytest.mark.asyncio
async def test_clearqueue_command():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.queue.clear = MagicMock()

    await bot.clearqueue.callback(interaction)

    interaction.guild.voice_client.queue.clear.assert_called_once()
    interaction.response.send_message.assert_called_with(
        "The music queue has been cleared.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_shuffle_command_success():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.queue.is_empty = False
    interaction.guild.voice_client.queue.shuffle = MagicMock()

    await bot.shuffle.callback(interaction)

    interaction.guild.voice_client.queue.shuffle.assert_called_once()
    interaction.response.send_message.assert_called_with(
        "The music queue has been shuffled.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_stop_command_success(guild_id, mock_bot_presence):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild_id = int(guild_id)

    interaction.guild.voice_client.disconnect = AsyncMock()
    interaction.guild.voice_client.queue.clear = MagicMock()
    bot.ACTIVE_PLAYERS[str(guild_id)] = AsyncMock()

    await bot.stop.callback(interaction)

    interaction.guild.voice_client.queue.clear.assert_called_once()
    interaction.guild.voice_client.disconnect.assert_called_once()
    assert bot.ACTIVE_PLAYERS.get(str(guild_id)) is None
    mock_bot_presence.assert_called_once_with(activity=None)


@pytest.mark.asyncio
@patch("wavelink.Playable.search")
async def test_play_command_new_connection(mock_search, mock_track):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.user.voice.channel = MagicMock(spec=nextcord.VoiceChannel)
    interaction.followup.send = AsyncMock()

    mock_search.return_value = [mock_track]
    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.playing = False
    mock_player.queue = AsyncMock(spec=wavelink.Queue)

    interaction.guild.voice_client = None
    interaction.user.voice.channel.connect = AsyncMock(return_value=mock_player)

    await bot.play.callback(interaction, "Never Gonna Give You Up")

    interaction.user.voice.channel.connect.assert_called_once()
    mock_player.queue.put_wait.assert_called_once()
    mock_player.play.assert_called_once()
    assert interaction.followup.send.called


@pytest.mark.asyncio
@patch("wavelink.Playable.search")
async def test_play_command_no_results(mock_search):
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.defer = AsyncMock()
    interaction.user.voice.channel = MagicMock()
    interaction.followup.send = AsyncMock()

    mock_search.return_value = []
    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.queue = AsyncMock(spec=wavelink.Queue)
    mock_player.channel = interaction.user.voice.channel
    interaction.guild.voice_client = mock_player

    await bot.play.callback(interaction, "invalid_search_query_xyz")

    args, kwargs = interaction.followup.send.call_args
    assert args[0] == "No results found."
    mock_player.queue.put_wait.assert_not_called()
    mock_player.play.assert_not_called()


@pytest.mark.asyncio
async def test_nowplaying_command_playing():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()

    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.playing = True
    mock_player.position = 60000

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

    await bot.nowplaying.callback(interaction)

    interaction.response.send_message.assert_called_once()
    args, kwargs = interaction.response.send_message.call_args
    embed = kwargs.get("embed")
    assert embed.title == "💿 Currently Playing"
    assert embed.fields[0].value == "Test Author"


@pytest.mark.asyncio
async def test_ping_command():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    with patch("nextcord.Client.latency", new_callable=PropertyMock) as mock_latency:
        mock_latency.return_value = 0.05
        await bot.ping.callback(interaction)
        interaction.response.send_message.assert_called_with(
            "Pong! Latency: 50ms", ephemeral=True
        )


@pytest.mark.asyncio
async def test_regression_empty_channel_continues_playing_leak():
    """
    REGRESSION TEST: Proves that the bot currently leaks bandwidth by
    continuing to play music when a voice channel becomes empty.
    """
    # Setup mock event environment
    member = MagicMock(spec=nextcord.Member)
    member.bot = False
    member.guild.id = 111222333
    guild_id_str = str(member.guild.id)

    # Mock channel containing ONLY the bot (0 humans)
    mock_channel = MagicMock(spec=nextcord.VoiceChannel)
    bot_member = MagicMock(spec=nextcord.Member)
    bot_member.bot = True
    mock_channel.members = [bot_member]

    # Mock active player
    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.channel = mock_channel
    mock_player.playing = True
    mock_player.paused = False
    member.guild.voice_client = mock_player

    if not hasattr(bot.bot, "on_voice_state_update"):
        pytest.fail(
            "REGRESSION CONFIRMED: bot.bot has no 'on_voice_state_update'"
            "attribute. The bot will leak bandwidth in empty channels!"
        )

    # Create proper mock for the "before" state to trigger Scenario A
    mock_before = MagicMock()
    mock_before.channel = mock_channel

    # Fire the event listener (this will run once you patch bot.py)
    await bot.bot.on_voice_state_update(member, mock_before, MagicMock())

    # After patching, this assertion ensures the garbage collection task is generated
    assert (
        hasattr(bot, "AUTO_DISCONNECT_TASKS")
        and guild_id_str in bot.AUTO_DISCONNECT_TASKS
    )


@pytest.mark.asyncio
async def test_patch_v101_user_rejoin_cancels_countdown():
    """PATCH VERIFICATION:
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

    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.channel = mock_channel
    member.guild.voice_client = mock_player

    # Set up an active dummy countdown task
    async def dummy_timer():
        await asyncio.sleep(10)

    running_task = asyncio.create_task(dummy_timer())
    bot.AUTO_DISCONNECT_TASKS[guild_id_str] = running_task

    # Setup "after" state to trigger human rejoin logic (Scenario B)
    mock_after = MagicMock()
    mock_after.channel = mock_channel

    await bot.bot.on_voice_state_update(member, MagicMock(), mock_after)

    # Yield control to allow cancellation to propagate
    await asyncio.sleep(0)

    # Verify task was explicitly aborted
    assert running_task.cancelled() is True


@pytest.mark.asyncio
@patch("bot.ACTIVE_PLAYERS", new_callable=dict)
async def test_patch_v101_migration_helper_executes_clean_slate(mock_active_players):
    """
    INTEGRATION TEST: Verifies that when a bot is rescued from an idle channel,
    the patch kills the timer, wipes the queue, discards the track,
    and repositions smoothly.
    """
    guild_id = 123000123
    guild_id_str = str(guild_id)

    # Mock global interface components
    mock_embed_msg = AsyncMock(spec=nextcord.Message)
    mock_active_players[guild_id_str] = mock_embed_msg

    # Establish running countdown task to intercept
    async def dummy_timer():
        await asyncio.sleep(10)

    running_task = asyncio.create_task(dummy_timer())
    bot.AUTO_DISCONNECT_TASKS[guild_id_str] = running_task

    # Set up player with a dirty track list state
    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    old_room = MagicMock(spec=nextcord.VoiceChannel)
    old_room.members = [MagicMock(bot=True)]  # Alone
    mock_player.channel = old_room
    mock_player.queue = MagicMock()

    new_room = MagicMock(spec=nextcord.VoiceChannel)

    # EXECUTE CLEAN SLATE MIGRATION FLOW
    if len([m for m in mock_player.channel.members if not m.bot]) == 0:
        # A. Terminate task
        if guild_id_str in bot.AUTO_DISCONNECT_TASKS:
            bot.AUTO_DISCONNECT_TASKS[guild_id_str].cancel()

        # B. Eject state
        mock_player.queue.clear()
        await mock_player.skip()

        # C. Destroy old UI instance
        await mock_active_players[guild_id_str].delete()
        mock_active_players[guild_id_str] = None

        # D. Reposition lane
        await mock_player.move_to(new_room)

    # Yield control to allow cancellation to propagate
    await asyncio.sleep(0)

    # ASSERTIONS: Verify the leak state is eliminated entirely
    assert running_task.cancelled() is True
    mock_player.queue.clear.assert_called_once()
    mock_player.skip.assert_called_once()
    mock_embed_msg.delete.assert_called_once()
    mock_player.move_to.assert_called_with(new_room)
    assert mock_active_players[guild_id_str] is None


# --- 5. COMPREHENSIVE COMMAND & AUTOPLAY QA TEST SUITE ---


@pytest.mark.asyncio
async def test_join_command_user_not_in_voice():
    """Scenario: User triggers /join while not connected to any voice channel."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.user.voice = None  # User is not in voice

    await bot.join.callback(interaction)

    interaction.response.send_message.assert_called_once_with(
        "You must be in a voice channel to use this command.",
        ephemeral=True,
        delete_after=bot.MESSAGE_DELETE_TIMEOUT,
    )


@pytest.mark.asyncio
async def test_volume_command_no_voice_client():
    """Scenario: Setting volume when the bot has no active voice connection."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client = None

    await bot.volume.callback(interaction, value=75)

    interaction.response.send_message.assert_called_once_with(
        "I'm not connected to any voice channel.", ephemeral=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_volume", [-10, 101, 150])
async def test_volume_command_out_of_bounds_guards(invalid_volume):
    """
    Boundary Value Test:
    Setting volume at Input boundaries
    outside the strictly allowed 0-100 range.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    mock_vc = AsyncMock(spec=bot.WavelinkPlayer)
    interaction.guild.voice_client = mock_vc

    await bot.volume.callback(interaction, value=invalid_volume)

    interaction.response.send_message.assert_called_with(
        "Please provide a volume value between 0 and 100.", ephemeral=True
    )
    mock_vc.set_volume.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_volume", [0, 50, 100])
async def test_volume_command_success_boundaries(valid_volume):
    """
    Boundary Value Test:
    Setting volume at extreme or mid-range valid boundary limits.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    mock_vc = AsyncMock(spec=bot.WavelinkPlayer)
    mock_vc.set_volume = AsyncMock()
    interaction.guild.voice_client = mock_vc

    await bot.volume.callback(interaction, value=valid_volume)

    mock_vc.set_volume.assert_called_once_with(valid_volume)
    interaction.response.send_message.assert_called_once_with(
        f"Volume set to {valid_volume}%.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_loop_command_guard_when_not_playing():
    """Scenario: Toggling loop state when the player is idle."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    mock_vc = AsyncMock(spec=bot.WavelinkPlayer)
    mock_vc.playing = False
    interaction.guild.voice_client = mock_vc

    await bot.loop.callback(interaction)

    interaction.response.send_message.assert_called_once_with(
        "Nothing is currently playing to loop.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_loop_command_toggle_state_inversion():
    """
    Scenario:
    Confirm the loop boolean state flips
    and scales on back-to-back calls.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    mock_vc = AsyncMock(spec=bot.WavelinkPlayer)
    mock_vc.playing = True
    mock_vc.loop = False  # Start disabled
    interaction.guild.voice_client = mock_vc

    # First inversion pass: Enable loop
    await bot.loop.callback(interaction)
    assert mock_vc.loop is True
    interaction.response.send_message.assert_called_with(
        "Looping enabled for the current track.", ephemeral=True
    )

    # Second inversion pass: Disable loop
    await bot.loop.callback(interaction)
    assert mock_vc.loop is False
    interaction.response.send_message.assert_called_with(
        "Looping disabled for the current track.", ephemeral=True
    )


@pytest.mark.asyncio
async def test_autoplay_command_guard_when_disconnected():
    """Scenario: Setting autoplay options when disconnected from voice."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client = None

    await bot.autoplay.callback(interaction, mode="partial")

    interaction.response.send_message.assert_called_once_with(
        "I'm not connected to any voice channel.", ephemeral=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode_str, expected_enum",
    [
        ("enabled", wavelink.AutoPlayMode.enabled),
        ("partial", wavelink.AutoPlayMode.partial),
        ("disabled", wavelink.AutoPlayMode.disabled),
    ],
)
async def test_autoplay_command_and_global_persistence_mapping(mode_str, expected_enum):
    """Scenario: Passing inputs to verify enum translations and global map retention."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild_id = 999111222
    interaction.response.send_message = AsyncMock()

    mock_vc = AsyncMock(spec=bot.WavelinkPlayer)
    interaction.guild.voice_client = mock_vc

    guild_key = str(interaction.guild_id)
    bot.GUILD_AUTOPLAY_MODES.pop(guild_key, None)  # Purge old cache state

    await bot.autoplay.callback(interaction, mode=mode_str)

    # Validate setting reflects on player and global mapping registry
    assert bot.GUILD_AUTOPLAY_MODES[guild_key] == expected_enum
    assert mock_vc.autoplay == expected_enum
    interaction.response.send_message.assert_called_once_with(
        f"Autoplay mode has been set to: **{mode_str.capitalize()}**", ephemeral=True
    )


@pytest.mark.asyncio
async def test_on_wavelink_track_end_partial_empty_auto_queue_fallback():
    """
    INTEGRATION QA TEST: Assures that if user queue is empty and auto_queue
    has not populated yet under Partial Autoplay mode, it triggers a seed re-population.
    """
    mock_payload = MagicMock(spec=wavelink.TrackEndEventPayload)
    mock_payload.reason = "finished"

    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.guild.id = 555444333
    mock_player.autoplay = wavelink.AutoPlayMode.partial

    # Both active queues evaluate as fully dry
    mock_player.queue = MagicMock(spec=wavelink.Queue)
    mock_player.queue.is_empty = True
    mock_player.auto_queue = MagicMock(spec=wavelink.Queue)
    mock_player.auto_queue.is_empty = True

    mock_seed_track = MagicMock(spec=wavelink.Playable)
    mock_payload.track = mock_seed_track
    mock_payload.player = mock_player

    await bot.on_wavelink_track_end(mock_payload)

    mock_player.play.assert_called_once_with(
        mock_seed_track, populate=True, max_populate=5
    )
    mock_player.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_update_player_message_ignores_api_errors():
    """STRESS TEST: Ensures bot doesn't crash if the persistent message edit fails."""
    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.guild.id = 123
    mock_player.current = MagicMock(spec=wavelink.Playable)

    mock_msg = AsyncMock()
    # Simulate a Discord API error (e.g. message deleted or no permissions)
    mock_msg.edit.side_effect = nextcord.HTTPException(AsyncMock(), "Failed")

    bot.ACTIVE_PLAYERS["123"] = mock_msg

    # This call should catch the exception and return normally
    await bot.update_player_message(mock_player)
    mock_msg.edit.assert_called_once()


@pytest.mark.asyncio
async def test_join_restores_persisted_autoplay_mode():
    """
    INTEGRITY TEST:
    Verifies that joining a channel restores saved autoplay settings.
    """
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild_id = 456
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client = None
    interaction.user.voice.channel = AsyncMock(spec=nextcord.VoiceChannel)
    interaction.user.voice.channel.name = "Test Channel"

    mock_vc = AsyncMock(spec=bot.WavelinkPlayer)
    interaction.user.voice.channel.connect.return_value = mock_vc

    # Pre-set a mode in the persistent dictionary
    bot.GUILD_AUTOPLAY_MODES["456"] = wavelink.AutoPlayMode.partial

    await bot.join.callback(interaction)

    assert mock_vc.autoplay == wavelink.AutoPlayMode.partial


@pytest.mark.asyncio
@patch("bot.QueueSongList")
async def test_queue_command_enforces_recommendation_limit(mock_view_class):
    """STRESS TEST:
    Confirms UI slices recommendations even if internal queue is flooded."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.original_message = AsyncMock()
    interaction.guild_id = 123
    mock_player = AsyncMock(spec=bot.WavelinkPlayer)
    mock_player.autoplay = wavelink.AutoPlayMode.partial
    mock_player.queue = []
    mock_player.auto_queue = MagicMock(spec=wavelink.Queue)
    mock_player.auto_queue.is_empty = False
    tracks = [MagicMock(spec=wavelink.Playable) for _ in range(20)]
    mock_player.auto_queue.__iter__.return_value = iter(tracks)

    interaction.guild.voice_client = mock_player

    await bot.queue.callback(interaction)

    args, _ = mock_view_class.call_args
    songs_list = args[0]
    # Should be exactly 5 recommendations displayed
    assert len(songs_list) == 5
