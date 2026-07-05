"""
tests/test_connection.py
------------------------
Integration tests for Environment Configuration and System Connectivity.

Responsibility:
- Validates that the application has all necessary production configuration
  loaded (Tokens, Lavalink URI/Credentials).
- Serves as the foundation for future "System Health" checks (e.g., node
  heartbeat monitoring and automatic reconnection verification).

Usage:
- Run all tests: `pytest`
- Run this file: `pytest tests/test_connection.py`
"""

import os


def test_environment_variables_load():
    """QA: Verify that critical production config variables parse correctly."""
    assert os.getenv("BOT_TOKEN") is not None, "BOT_TOKEN environment variable missing"
    assert os.getenv("LAVALINK_URI") is not None, (
        "LAVALINK_URI environment variable missing"
    )
    "LAVALINK_URI environment variable missing"
    assert os.getenv("LAVALINK_PASSWORD") is not None, (
        "LAVALINK_PASSWORD environment variable missing"
    )
