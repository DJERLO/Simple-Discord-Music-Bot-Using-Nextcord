import nextcord
from nextcord.ext import commands
import inspect

class Help(commands.Cog):
    """
    A dynamic help command for the bot.
    
    Usage:
    `/help` - Lists all available commands.
    `/help <command_name>` - Displays details for a specific command.
    
    Example:
    `/help` - Lists all available commands.
    `/help ping` - Displays details for the `ping` command.
    
    Note:
    - If no command name is provided, the bot will list all available commands.
    - If a valid command name is provided, the bot will display details for that command.
    """
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(name="help", description="View all available commands or get details on a specific one")
    async def help(self, interaction: nextcord.Interaction, command_name: str = None):
        await interaction.response.defer(ephemeral=True)
        
        # 1. Fetch all commands
        all_commands = self.bot.get_all_application_commands()

        if command_name:
            # Show details for specific command
            cmd = next((c for c in all_commands if c.name == command_name), None)
            if cmd:
                embed = nextcord.Embed(title=f"/{cmd.name}", description=inspect.cleandoc(cmd.callback.__doc__ or "No description provided."), color=0xfc0404)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("Command not found.", ephemeral=True)
        else:
            # Show general index
            embed = nextcord.Embed(title="Bot Help Index", description="List of available commands:", color=0xfc0404)
            for cmd in all_commands:
                # Truncate docstring to show only the first line in the list
                short_desc = inspect.cleandoc(cmd.callback.__doc__ or "No description").split('\n')[0]
                embed.add_field(name=f"/{cmd.name}", value=short_desc, inline=False)
            
            await interaction.followup.send(embed=embed)

def setup(bot):
    bot.add_cog(Help(bot))