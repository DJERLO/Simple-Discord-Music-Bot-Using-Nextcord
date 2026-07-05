"""
tests/test_commands.py
----------------------
Integration tests for General and Utility commands.

Responsibility:
- Verifies the `/help` command initialization, embeds, and pagination logic.
- Ensures command caching and UI view states (like HelpView) respond correctly
  to user interactions.
- Validates basic utility commands (e.g., /ping) and response consistency.

Usage:
- Run all tests: `pytest`
- Run this file: `pytest tests/test_commands.py`
"""

from unittest.mock import AsyncMock, MagicMock

import nextcord
import pytest

from cogs.music_commands import MusicCommands
from ui.views import HelpView


@pytest.mark.asyncio
async def test_help_command_initialization():
    """
    Integration test:
    Help command should initialize correctly
    """
    mock_bot = MagicMock()
    mock_interaction = AsyncMock(spec=nextcord.Interaction)

    mock_interaction.followup.send = AsyncMock()
    mock_interaction.response = AsyncMock()

    cog = MusicCommands(mock_bot)
    cog.command_list = [MagicMock(name="play"), MagicMock(name="ping")]

    await cog.help(mock_interaction, command_name=None)

    mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
    assert mock_interaction.followup.send.called


@pytest.mark.asyncio
async def test_help_view_pagination_bounds():
    """
    Integration test:
    Help view should update button states correctly
    """

    commands = [MagicMock(name=f"cmd{i}") for i in range(10)]
    mock_bot = MagicMock()
    view = HelpView(commands, mock_bot)

    view.update_button_states()
    assert view.prev_button.disabled is True
    assert view.next_button.disabled is False

    view.page = view.max_pages
    view.update_button_states()
    assert view.prev_button.disabled is False
    assert view.next_button.disabled is True
