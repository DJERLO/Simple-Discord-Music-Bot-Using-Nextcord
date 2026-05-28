# Simple Discord Music Bot Using Nextcord

A simple yet feature-rich Discord music bot I built with [Nextcord](https://github.com/nextcord/nextcord) and [yt-dlp](https://github.com/yt-dlp/yt-dlp).
It supports music playback, queue management, and interactive slash commands.

This project was heavily inspired by [CreepyD](https://www.youtube.com/watch?v=U5CUkxUh2CQ), who made a similar bot using [discord.py](https://github.com/Rapptz/discord.py) in Python.
For my version, I used **Nextcord** as the main Discord API wrapper.

---

## Features

* Play songs or playlists from YouTube
* Queue management (add, view, skip, pause, resume, stop)
* Interactive queue display
* Playlist support
* Slash commands for all actions

---

## Setup

1. **Clone the repository**

   ```bash
   git clone <repo-url>
   cd <repo-directory>
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file in the project root and add your Discord bot token:

   ```env
   BOT_TOKEN=your_discord_bot_token
   ```

4. **Install FFmpeg**
   Make sure FFmpeg is either:

   * Located at `bin/ffmpeg/ffmpeg.exe`, **or**
   * Added to your system `PATH`.

---

## Usage

Run the bot with:

```bash
python bot.py
```

---

## Slash Commands

* `/play <song or playlist>` — Play a song or add it to the queue
* `/skip` — Skip the current song
* `/pause` — Pause playback
* `/resume` — Resume playback
* `/stop` — Stop playback and clear the queue
* `/queue` — Show the current queue

---

## Extending (Future Ideas?!)

Check the `TODO` comments in the code for possible improvements:

* Shuffle
* Repeat
* Better error handling
* More queue management features

---

## License

This project is licensed under the [MIT License](LICENSE).

---
