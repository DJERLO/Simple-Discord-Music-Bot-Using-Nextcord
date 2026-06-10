import nextcord
from nextcord.ext import application_checks


def has_dj_permissions():
    """
    A custom Nextcord application command check decorator.
    Allows execution if the user is the Server Owner, an Administrator,
    or possesses a role explicitly named 'DJ' (case-insensitive).
    """

    async def predicate(interaction: nextcord.Interaction) -> bool:
        # 1. Bypass check: Server Owner
        if interaction.user.id == interaction.guild.owner_id:
            return True

        # 2. Bypass check: Administrator permissions
        if interaction.user.guild_permissions.administrator:
            return True

        # 3. Role check: Possesses a role named "DJ" (case-insensitive)
        has_dj_role = any(role.name.lower() == "dj" for role in interaction.user.roles)
        if has_dj_role:
            return True

        # If all checks fail, raise an ApplicationCheckFailure
        raise nextcord.errors.ApplicationCheckFailure(
            "❌ **Access Denied:** "
            "You need the **DJ** role or **Administrator** "
            "permissions to use this command."
        )

    return application_checks.check(predicate)
