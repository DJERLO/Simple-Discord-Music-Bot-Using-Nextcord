"""
core/permissions.py

This module contains functions for checking permissions in Discord servers.

Functions:
---------
is_owner(interaction: nextcord.Interaction) -> bool
    Returns True if the user is the server owner.
is_admin(interaction: nextcord.Interaction) -> bool
    Returns True if the user is an administrator.
is_dj(interaction: nextcord.Interaction) -> bool
    Returns True if the user is a DJ, Admin, or Owner.
"""

import nextcord


async def is_owner(interaction: nextcord.Interaction) -> bool:
    """
    Returns True if the user is the server owner.

    Args:
        interaction (nextcord.Interaction): The interaction object.

    Returns:
        bool: True if the user is the server owner, False otherwise.
    """
    return interaction.user.id == interaction.guild.owner_id


async def is_admin(interaction: nextcord.Interaction) -> bool:
    """
    Returns True if the user is an administrator.

    Args:
        interaction (nextcord.Interaction): The interaction object.

    Returns:
        bool: True if the user is an administrator, False otherwise.
    """
    return interaction.user.guild_permissions.administrator


async def is_dj(interaction: nextcord.Interaction) -> bool:
    """
    Returns True if the user is a DJ, Admin, or Owner.

    Args:
        interaction (nextcord.Interaction): The interaction object.

    Returns:
        bool: True if the user is a DJ, Admin, or Owner, False otherwise.
    """
    if await is_owner(interaction):
        return True
    if await is_admin(interaction):
        return True
    return any(role.name.lower() == "dj" for role in interaction.user.roles)
