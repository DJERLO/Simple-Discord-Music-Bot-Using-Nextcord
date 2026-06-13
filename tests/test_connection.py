import os


def test_environment_variables_load():
    """QA: Verify that critical production config variables parse correctly."""
    assert os.getenv("LAVALINK_URI") is not None, (
        "LAVALINK_URI environment variable missing"
    )
    "LAVALINK_URI environment variable missing"
    assert os.getenv("LAVALINK_PASSWORD") is not None, (
        "LAVALINK_PASSWORD environment variable missing"
    )
