import os

import nextcord
import wavelink
from dotenv import load_dotenv
from nextcord.ext import commands

from core.logging import get_logger
from core.setup import create_node

# Load variables from the .env file
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
lavalink_uri = os.getenv("LAVALINK_URI", "http://127.0.0.1:2333")
lavalink_password = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

logger = get_logger(__name__)

# Configure bot client instance intents
intents = nextcord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    """Connect to Lavalink node when the bot is ready and sync commands."""
    logger.info(f"🚀 Main Engine Online: Authenticated as {bot.user}")

    node = create_node()
    await wavelink.Pool.connect(nodes=[node], client=bot)
    await bot.sync_application_commands()


# Registered Extension Modules
extensions = ["cogs.events", "cogs.music_commands"]

if __name__ == "__main__":
    for extension in extensions:
        try:
            bot.load_extension(extension)
            logger.info(f"✔ Extension mounted successfully: {extension}")
        except Exception as e:
            logger.error(f"❌ Critical error loading extension {extension}: {e}")

    bot.run(bot_token)
