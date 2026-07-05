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
async def test_dj_permission_logic_pass_scenarios():
    """QA: Test logic boundaries for Owner, Admin, and DJ Role."""
    decorator = has_dj_permissions()
    predicate = decorator.predicate

    interaction = AsyncMock(spec=nextcord.Interaction)
    interaction.user.roles = []
    interaction.user.guild_permissions.administrator = False

    # 1. Server Owner
    interaction.user.id = 1
    interaction.guild.owner_id = 1
    assert await predicate(interaction) is True

    # 2. Administrator
    interaction.user.id = 2
    interaction.guild.owner_id = 1
    interaction.user.guild_permissions.administrator = True
    assert await predicate(interaction) is True

    # 3. DJ Role (Case Insensitive)
    interaction.user.guild_permissions.administrator = False
    dj_role = MagicMock()
    dj_role.name = "dJ"
    interaction.user.roles = [dj_role]
    assert await predicate(interaction) is True

    # 4. Access Denied
    interaction.user.roles = [MagicMock(name="Member")]
    with pytest.raises(nextcord.errors.ApplicationCheckFailure):
        await predicate(interaction)
