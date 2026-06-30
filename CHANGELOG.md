# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-06-30

### Added
- **Self-Healing Infrastructure**: Added autonomous Lavalink session recovery (`wavelink.Pool.close()`) to handle stale sessions, node drops, and `ChannelTimeoutException` without requiring manual bot restarts.
- **Persistent Dashboard**: Implemented a resilient persistent player dashboard in `ui/embeds.py` utilizing an "Edit-if-exists, Send-if-not" pattern to maintain interaction stability and avoid message flicker or API spam.
- **Enhanced Logging**: Added a custom `ColorFormatter` in `core/logging.py` for high-visibility terminal debugging alongside plain-text rotating file persistence.
- **Troubleshooting & Privacy/Legal**: Appended troubleshooting guides and platform compliance statements to `README.MD`.

### Changed
- **Dependency Management**: Migrated the entire project's build and dependency orchestration from `pip` to `uv`, standardizing test execution to `uv run pytest` and `uv run ptw`.
- **Event-Driven Lifecycle**: Transitioned voice state updates from fragile legacy hacks to native Wavelink persistent event listeners (`on_wavelink_node_ready`, `on_wavelink_node_closed`).
- **Interaction Stability**: Standardized all command endpoints to use deferred ephemeral responses followed by `followup.send()` to prevent interaction timeouts.
- **Module Documentation**: Added extensive, standardized Google-style docstrings and origin tracking to all functions, cogs, UI components, and core modules to enhance IDE intellisense and code readability.

### Fixed
- Resolved 300-second disconnect bug and phantom drops caused by Wavelink inactivity tokens by manually managing token buckets and occupancy checks during rapid skips.
- Fixed track-skipping logic to ensure manual jumps play the intended next track from the queue rather than repeating payloads.
- Added strict connectivity guard checks (`_is_node_ready`) to block command execution when the music engine is offline, preventing zombie tasks.

---

## [1.1.0] - 2026-06-14

### Added
- **Autoplay Engine**: Global per-guild memory registers for persistent user preferences.
- **Navigation**: `/previous` track command and unified history tracking.
- **Governance**: Implemented `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, and standardized repository licensing.
- **Documentation**: Overhauled docs with dedicated guides for VPS deployment, Linting (Ruff), and Testing (Pytest) via Mintlify.
- **Testing**: Scaled test suite to 38 high-fidelity cases with 100% logic verification.

### Changed
- **Architecture**: Modularized codebase from monolith into domain-specific Cogs.
- **Infrastructure**: Integrated parallel multi-version CI pipeline (Python 3.12–3.14-dev) and automated dependency tracking (Dependabot).
- **Security**: Restricted GitHub Action permissions to `contents: read` (Principle of Least Privilege).

### Fixed
- Resolved `/skip` autoplay race conditions and UI "ghost" data issues during channel moves.

---

## [1.0.1] - 2026-06-09

### Changed
- **Security**: Hardened GitHub Action pipeline security.

### Fixed
- **Stability**: Implemented auto-disconnect logic for empty voice channels to prevent bandwidth leakage.
- **Maintenance**: Automated dependency tracking via Dependabot for pip and docker-compose.

---

## [1.0.0-beta.1] - 2026-06-03

### Added
- **Engine Migration**: Shifted audio streaming from local FFmpeg/yt-dlp to Lavalink/Wavelink.
- **CI/CD**: Implemented parallel build matrix and automated Ruff linting pipeline.
- **Testing**: Initialized full asynchronous unit test suite using pytest.

---

## [0.1.0] - 2025-07-21

### Added
- Initial project foundation (Music bot prototype).
- Basic song playback notifications.