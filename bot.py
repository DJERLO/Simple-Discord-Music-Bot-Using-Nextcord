import os
import asyncio
from dotenv import load_dotenv 
import nextcord
from nextcord.ext import commands
from nextcord import Interaction
import yt_dlp
from collections import deque
from views import QueueView as QueueSongList

# Load variables from the .env file
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')

# Function to search for a song using yt-dlp
async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

# Set up the bot with the necessary intents
intents = nextcord.Intents.default()
intents.message_content = True  # Enables the message content intent

bot = commands.Bot(command_prefix='/', intents=intents)

# Create the structure for queueing songs - Dictionary of queues
SONG_QUEUES = {}

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    print('Syncing slash commands...')
    await bot.sync_application_commands()
    print('Slash commands synced.')

# Slash Command to skip the current song
@bot.slash_command(name="skip", description="Skips the current playing song")
async def skip(interaction: Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")

# Slash Command to pause the currently playing song
@bot.slash_command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")

    # Check if something is actually playing
    if not voice_client.is_playing():
        return await interaction.response.send_message("Nothing is currently playing.")
    
    # Pause the track
    voice_client.pause()
    await interaction.response.send_message("Playback paused!")

# Slash Command to resume the currently paused song
@bot.slash_command(name="resume", description="Resume the currently paused song.")
async def resume(interaction: Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")

    # Check if it's actually paused
    if not voice_client.is_paused():
        return await interaction.response.send_message("I’m not paused right now.")
    
    # Resume playback
    voice_client.resume()
    await interaction.response.send_message("Playback resumed!")

# Slash Command to stop playback and clear the queue
@bot.slash_command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("I'm not connected to any voice channel.")

    # Clear the guild's queue
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    # If something is playing or paused, stop it
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    # (Optional) Disconnect from the channel
    await voice_client.disconnect()

    await interaction.response.send_message("Stopped playback and disconnected!")

@bot.slash_command(name="play", description="Play a song or add it to the queue.")
async def play(interaction: Interaction, song_query: str):
    await interaction.response.defer()

    guild_id = str(interaction.guild_id)
    voice_channel = interaction.user.voice.channel

    if voice_channel is None:
        await interaction.followup.send("You must be in a voice channel.")
        return

    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": True,
        "quiet": True,                #  Suppress all console output
        "no_warnings": True,          #  Suppress warnings
        "logtostderr": False,         #  Don't log to stderr
        "ignoreerrors": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    }

    # Check if the query is a playlist
    if "youtube.com/playlist" in song_query or "&list=" in song_query:
        query = song_query  # Let yt-dlp process the playlist
    else:
        query = f"ytsearch1:{song_query}"  # Normal search

    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])

    if tracks is None:
        await interaction.followup.send("No results found.")
        return

    if not tracks:
        await interaction.followup.send("No results found.")
        return
    
    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    for index, track in enumerate(tracks):
        audio_url = track.get("url")
        title = track.get("title", "Untitled")
        webpage_url = track.get("webpage_url")
        thumbnail = track.get("thumbnail")

        SONG_QUEUES[guild_id].append((audio_url, title, webpage_url, thumbnail))

    if voice_client.is_playing() or voice_client.is_paused():
         # If something is already playing, just add to the queue
        
        first_track = tracks[0]
        embed = nextcord.Embed(
            title="Added to Queue",
            description=(
                f"Added a playlist with **{len(tracks)}** tracks." if len(tracks) > 1 
                else f"[{first_track.get('title', 'Untitled')}]({first_track.get('webpage_url')})"
            ),
            color=nextcord.Color.orange()
        )
        embed.set_image(url=first_track.get("thumbnail"))
        embed.set_footer(
            text=f"Requested by {interaction.user.display_name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )

        await interaction.followup.send(embed=embed)
    else:
        # If nothing is playing, start playing the first song
        await interaction.followup.send(f"Playing: **{tracks[0].get('title', 'Untitled')}**", ephemeral=True)
        await play_next_song(voice_client, guild_id, interaction.channel)

async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title, webpage_url, thumbnail = SONG_QUEUES[guild_id].popleft()

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k",
            
        }

        # Remove executable if FFmpeg is in PATH
        ffmpeg_path = os.path.join("bin", "ffmpeg", "ffmpeg.exe")
        source = nextcord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable=ffmpeg_path)

         # Set bot activity
        await bot.change_presence(
            activity=nextcord.Activity(type=nextcord.ActivityType.listening, name=title, url=webpage_url)
        )

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_play)
        embed = nextcord.Embed(
            title="Now Playing:",
            description=f"[{title}]({webpage_url})",
            color=nextcord.Color.green()
        )
        embed.set_image(url=thumbnail)

        asyncio.create_task(channel.send(embed=embed))
    else:
        await voice_client.disconnect()
        await bot.change_presence(activity=None)
        SONG_QUEUES[guild_id] = deque()

@bot.slash_command(name="queue", description="Show the current music queue.")
async def queue(interaction: Interaction):
    guild_id = str(interaction.guild_id)
    if guild_id not in SONG_QUEUES or not SONG_QUEUES[guild_id]:
        await interaction.response.send_message("The queue is currently empty.", ephemeral=True)
        return

    songs_list = list(SONG_QUEUES[guild_id])  # Make a copy
    view = QueueSongList(songs_list, interaction.user, guild_id)
    await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)


# Run the bot with your token
bot.run(bot_token)