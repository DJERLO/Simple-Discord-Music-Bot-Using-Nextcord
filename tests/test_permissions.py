"""
tests/test_permissions.py
-------------------------
Integration and Unit tests for Access Control and Voting Logic.

Responsibility:
- Validates the DJ permission system (Owner, Administrator, and custom DJ roles).
- Ensures vote-skipping logic handles threshold calculations correctly.
- Verifies that unauthorized users are correctly restricted via ApplicationCheckFailure.

Usage:
- Run all tests: `pytest`
- Run this file: `pytest tests/test_permissions.py`
"""

from unittest.mock import AsyncMock, MagicMock

import nextcord
import pytest

from cogs.music_commands import WavelinkPlayer
from core.decorators import has_dj_permissions
from ui.embeds import VOTE_SKIPS


@pytest.mark.asyncio
async def test_voteskip_logic_immediate_solo(cog):
    """QA: Ensure 1 listener triggers an immediate skip without voting delay."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild_id = 123
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.channel = MagicMock(spec=nextcord.VoiceChannel)
    mock_vc.playing = True
    mock_vc.channel.members = [MagicMock(bot=False)]  # Only the requester
    interaction.guild.voice_client = mock_vc
    interaction.user.voice.channel = mock_vc.channel

    await cog.voteskip.callback(cog, interaction)

    mock_vc.skip.assert_called_once()
    assert "Skipping track immediately!" in interaction.followup.send.call_args[0][0]


@pytest.mark.asyncio
async def test_voteskip_logic_threshold_met(cog):
    """QA: Verify 50% majority requirement (2/2 listeners) triggers a skip."""
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.guild_id = 456
    interaction.user.id = 101
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    mock_vc = AsyncMock(spec=WavelinkPlayer)
    mock_vc.channel = MagicMock(spec=nextcord.VoiceChannel)
    mock_vc.playing = True

    m1 = MagicMock(bot=False, id=101)
    m2 = MagicMock(bot=False, id=202)
    mock_vc.channel.members = [m1, m2]
    interaction.guild.voice_client = mock_vc
    interaction.user.voice.channel = mock_vc.channel

    await cog.voteskip.callback(cog, interaction)
    assert 101 in VOTE_SKIPS["456"]
    mock_vc.skip.assert_not_called()

    interaction.user.id = 202
    await cog.voteskip.callback(cog, interaction)
    mock_vc.skip.assert_called_once()
    assert VOTE_SKIPS["456"] == set()


@pytest.mark.asyncio
async def test_has_dj_permissions_logic():
    """QA: Test decorator logic for Owner, Admin, DJ, and Restricted users."""

    # 1. Setup Mock Interaction
    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.user = MagicMock()
    interaction.guild = MagicMock()
    interaction.response = AsyncMock()

    # Define a dummy command to decorate, simulating a Cog method (self, interaction)
    @has_dj_permissions()
    async def dummy_command(self, interaction):
        return "SUCCESS"

    # --- SCENARIOS ---

    # Setup: Unauthorized User (Member)
    interaction.user.roles = [MagicMock(name="Member")]
    interaction.user.guild_permissions.administrator = False

    # 4. Access Denied (Expect response to be sent)
    await dummy_command(None, interaction)

    # Verify unauthorized access sends an ephemeral message
    interaction.response.send_message.assert_called_once()
    assert "Access Denied" in interaction.response.send_message.call_args[0][0]

    # 1. Server Owner (Expect success)
    interaction.user.id = 1
    interaction.guild.owner_id = 1
    interaction.response.send_message.reset_mock()
    assert await dummy_command(None, interaction) == "SUCCESS"
    interaction.response.send_message.assert_not_called()

    # 2. Administrator (Expect success)
    interaction.user.id = 2
    interaction.user.guild_permissions.administrator = True
    assert await dummy_command(None, interaction) == "SUCCESS"
