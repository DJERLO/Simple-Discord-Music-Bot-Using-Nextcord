# Simple Discord Music Bot Using Nextcord

A simple yet feature-rich Discord music bot I built with [Nextcord](https://github.com/nextcord/nextcord) and [yt-dlp](https://github.com/yt-dlp/yt-dlp).
It supports music playback, queue management, and interactive slash commands.

This project was heavily inspired by [CreepyD](https://www.youtube.com/watch?v=U5CUkxUh2CQ), who made a similar bot using [discord.py](https://github.com/Rapptz/discord.py) in Python.
For my version, I used **Nextcord** as the main Discord API wrapper.

---

## Features

* **High-Fidelity Playback:** Stream individual tracks or complete playlists directly from YouTube via `yt-dlp`.
* **State Persistence UI:** Displays interactive "Now Playing" rich embed updates straight to active server voice channels.
* **Paginated Navigation:** View deep music tracks using an organized, session-locked pagination view.
* **Graceful Session Lifecycles:** Safe server cleanup loops that free up memory allocations upon disconnecting.

---

## Architecture Dependencies

To implement this audio platform local testing pipeline successfully, your environment requires a binary mapping for **FFmpeg**. Without setting up this layout in your root project architecture, streaming audio streams onto voice sessions will fail.

## ⚡ Crucial Prerequisite: FFmpeg Installation

> ⚠️ **CRITICAL FOR TESTING:** This music bot **will not work** and will throw errors during playback if the FFmpeg binaries are missing from the project directory. 

Before trying to test the music bot, you must download the FFmpeg essentials build for Windows and place the executables inside the codebase workspace structure:

1. Create a folder named `bin` in your project root, and a folder named `ffmpeg` inside it (`bin/ffmpeg/`).
2. Download the FFmpeg binaries and copy `ffmpeg.exe`, `ffplay.exe`, and `ffprobe.exe` directly into that folder.

Your project file tree structure **must** look exactly like this to test playback:
```text
testbot/
├── bin/
│   └── ffmpeg/
│       ├── ffmpeg.exe      <-- Required
│       ├── ffplay.exe      <-- Required
│       └── ffprobe.exe     <-- Required
├── bot.py
├── views.py
├── .env
└── requirements.txt
```
*(Note: These heavy binary .exe files are configured via .gitignore to prevent them from hitting your remote GitHub storage limits).*


## Features

* **High-Quality Streaming:** Utilizes `yt-dlp` to extract and process audio feeds safely.
* **Smart Presence Indicators:** Shows the currently playing track live as a Discord Streaming activity status.
* **Persistent Display Cleanup:** Automatically destroys active embed tracking modules when streams stop to keep chat rooms clean.
* **Interactive Interface:** Built-in paginated system for inspecting extensive server queue structures seamlessly.
* **Graceful Session Restarts:** Includes a clean process-manager friendly restart routine instead of a hard, loop-breaking crash.

---

## Slash Commands

* `/play <song or playlist>` — Streams a song directly or queues up an entire YouTube playlist link.
* `/skip` — Skips the track currently active in the channel.
* `/pause` — Pauses current audio playback.
* `/resume` — Resumes paused music tracking.
* `/queue` — Launches a paginated interactive embed panel to browse the active song queue.
* `/stop` — Safely halts active audio, clears internal arrays, and cleanly drops voice server gateway connections.
* `/restart` — Clears server instances, releases voice nodes gracefully, and forces a seamless session reload (Admin Only).

---

## Usage

Run the bot with:

```bash
python bot.py
```
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
