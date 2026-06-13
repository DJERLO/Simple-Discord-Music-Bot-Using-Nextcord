from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
import wavelink

from bot import bot as bot_instance
from cogs.music_commands import MusicCommands
from ui.embeds import ACTIVE_PLAYERS, AUTO_DISCONNECT_TASKS, VOTE_SKIPS


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
    with patch.object(bot_instance, "change_presence", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture(autouse=True)
def clean_active_players():
    ACTIVE_PLAYERS.clear()
    AUTO_DISCONNECT_TASKS.clear()
    VOTE_SKIPS.clear()
    yield
    ACTIVE_PLAYERS.clear()


@pytest.fixture
def cog():
    return MusicCommands(bot_instance)
