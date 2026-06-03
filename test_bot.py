import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import wavelink
import nextcord

# Import the bot and view modules
import bot
from views import QueueView

# --- Fixtures ---

@pytest.fixture
def songs():
    return [
        ("https://link1.com", "Song Alpha", None, 125),
        ("https://link2.com", "Song Beta", None, 300),
        ("https://link3.com", "Song Gamma", None, 45)
    ]

@pytest.fixture
def mock_track():
    track = MagicMock(spec=wavelink.Playable)
    track.title = "Test Song"
    track.length = 180000 # 3 mins
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
    
    assert view.prev_page.disabled is True, "Previous button should be disabled on page 1"
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
    interaction.response.send_message.assert_called_with("Skipped the current song.", ephemeral=True)

@pytest.mark.asyncio
async def test_pause_command_success():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.playing = True
    interaction.guild.voice_client.pause = AsyncMock()
    
    await bot.pause.callback(interaction)
    
    interaction.guild.voice_client.pause.assert_called_once_with(True)
    interaction.response.send_message.assert_called_with("Playback paused!", ephemeral=True)

@pytest.mark.asyncio
async def test_resume_command_success():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.paused = True
    interaction.guild.voice_client.pause = AsyncMock()
    
    await bot.resume.callback(interaction)
    
    interaction.guild.voice_client.pause.assert_called_once_with(False)
    interaction.response.send_message.assert_called_with("Playback resumed!", ephemeral=True)

@pytest.mark.asyncio
async def test_clearqueue_command():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.queue.clear = MagicMock()
    
    await bot.clearqueue.callback(interaction)
    
    interaction.guild.voice_client.queue.clear.assert_called_once()
    interaction.response.send_message.assert_called_with("The music queue has been cleared.", ephemeral=True)

@pytest.mark.asyncio
async def test_shuffle_command_success():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    interaction.guild.voice_client.queue.is_empty = False
    interaction.guild.voice_client.queue.shuffle = MagicMock()
    
    await bot.shuffle.callback(interaction)
    
    interaction.guild.voice_client.queue.shuffle.assert_called_once()
    interaction.response.send_message.assert_called_with("The music queue has been shuffled.", ephemeral=True)

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
    embed = kwargs.get('embed')
    assert embed.title == "💿 Currently Playing"
    assert embed.fields[0].value == "Test Author"

@pytest.mark.asyncio
async def test_ping_command():
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.response.send_message = AsyncMock()
    with patch("nextcord.Client.latency", new_callable=PropertyMock) as mock_latency:
        mock_latency.return_value = 0.05
        await bot.ping.callback(interaction)
        interaction.response.send_message.assert_called_with("Pong! Latency: 50ms", ephemeral=True)