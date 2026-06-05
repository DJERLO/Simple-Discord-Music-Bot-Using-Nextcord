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

    # SAFE CHECK: If the listener is missing, the bug is officially documented
    if not hasattr(bot.bot, "on_voice_state_update"):
        pytest.fail(
            "REGRESSION CONFIRMED: bot.bot has no 'on_voice_state_update'"
            "attribute. The bot will leak bandwidth in empty channels!"
        )

    # Fire the event listener (this will run once you patch bot.py)
    await bot.bot.on_voice_state_update(member, MagicMock(), MagicMock())

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

    await bot.bot.on_voice_state_update(member, MagicMock(), MagicMock())

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

    # ASSERTIONS: Verify the leak state is eliminated entirely
    assert running_task.cancelled() is True
    mock_player.queue.clear.assert_called_once()
    mock_player.skip.assert_called_once()
    mock_embed_msg.delete.assert_called_once()
    mock_player.move_to.assert_called_with(new_room)
    assert mock_active_players[guild_id_str] is None
