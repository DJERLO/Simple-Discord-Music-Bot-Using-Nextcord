from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest
import wavelink

from bot import bot as bot_instance
from cogs.music_commands import MusicCommands


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
def mock_get_tracks():
    """
    Returns a list of tuples (uri, title, thumbnail, length)
    This is from the `get_tracks` function at core/utils.py
    Usage:
    - mock_get_tracks(mock_player)

    Returns:
    - list[tuple[str, str, str, int]]
    """
    return [
        ("https://link1.com", "Song Title 1", "thumbnail1", 180),
        ("https://link2.com", "Song Title 2", "thumbnail2", 210),
    ]


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


def patch_wavelink_connected():
    """Returns a patch context that makes the Wavelink Pool appear connected."""
    mock_node = MagicMock()
    mock_node.status = wavelink.NodeStatus.CONNECTED
    # Patch the dictionary lookup that _is_node_ready uses
    return patch("wavelink.Pool.nodes", {"test_node": mock_node})


@pytest.fixture
def cog():
    return MusicCommands(bot_instance)
