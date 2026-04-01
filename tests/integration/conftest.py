"""Integration test fixtures for Lexicon API.

Manages Lexicon app lifecycle and database state so integration tests
run against a clean, empty library.

On macOS, Lexicon is quit/launched automatically via AppleScript.
On other platforms, the user is prompted to quit/launch Lexicon manually.

Note: The Lexicon local API must be enabled in Lexicon settings for tests to connect.
"""

import os
import platform
import struct
import subprocess
import time
import wave
from pathlib import Path

import pytest
import requests

from lexicon import Lexicon, LEXICON_PORT, DEFAULT_HOST

IS_MACOS = platform.system() == "Darwin"

IS_WINDOWS = platform.system() == "Windows"

if IS_MACOS:
    LEXICON_DATA_DIR = os.path.expanduser("~/Library/Application Support/lexicon")
elif IS_WINDOWS:
    LEXICON_DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "Lexicon")
else:
    LEXICON_DATA_DIR = os.environ.get("LEXICON_DATA_DIR", "")
    if not LEXICON_DATA_DIR:
        pytest.skip(
            "Set LEXICON_DATA_DIR environment variable to the Lexicon data directory",
            allow_module_level=True,
        )

MAIN_DB_PATH = os.path.join(LEXICON_DATA_DIR, "main.db")
DB_BACKUP_PATH = os.path.join(LEXICON_DATA_DIR, "main.db.integration-backup")
API_URL = f"http://{DEFAULT_HOST}:{LEXICON_PORT}/v1/tracks"
LEXICON_APP_NAME = "Lexicon"

STARTUP_TIMEOUT = 10
SHUTDOWN_TIMEOUT = 10
POLL_INTERVAL = 1


def _is_api_ready() -> bool:
    """Check if the Lexicon API is responding."""
    try:
        resp = requests.get(API_URL, timeout=2)
        return resp.status_code in (200, 400)
    except (requests.ConnectionError, requests.Timeout):
        return False


def _wait_for_api(ready: bool, timeout: int):
    """Poll until the API matches the expected state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_api_ready() == ready:
            return
        time.sleep(POLL_INTERVAL)
    if ready:
        raise TimeoutError(
            "Lexicon API did not become ready in time. "
            "Make sure the local API is enabled in Lexicon settings."
        )
    raise TimeoutError(
        "Lexicon did not shut down in time. "
        "Please close it manually and re-run."
    )


def _quit_lexicon():
    """Quit Lexicon. Uses AppleScript on macOS, prompts otherwise."""
    if IS_MACOS:
        subprocess.run(
            ["osascript", "-e", f'tell application "{LEXICON_APP_NAME}" to quit'],
            capture_output=True,
        )
    else:
        input("Please quit Lexicon, then press Enter...")
    _wait_for_api(ready=False, timeout=SHUTDOWN_TIMEOUT)


def _launch_lexicon():
    """Launch Lexicon. Uses `open` on macOS, prompts otherwise."""
    if IS_MACOS:
        time.sleep(1)  # Allow Lexicon to fully exit before relaunching
        subprocess.run(
            ["open", "-a", LEXICON_APP_NAME],
            capture_output=True,
        )
    else:
        input("Please launch Lexicon, then press Enter...")
    _wait_for_api(ready=True, timeout=STARTUP_TIMEOUT)


def _backup_db():
    """Back up the current main.db by renaming it."""
    if os.path.islink(MAIN_DB_PATH) or os.path.exists(MAIN_DB_PATH):
        os.rename(MAIN_DB_PATH, DB_BACKUP_PATH)
    else:
        raise FileNotFoundError(f"No database found at {MAIN_DB_PATH}")


def _restore_db():
    """Restore the original main.db from backup."""
    if not os.path.exists(DB_BACKUP_PATH) and not os.path.islink(DB_BACKUP_PATH):
        return
    if os.path.islink(MAIN_DB_PATH) or os.path.exists(MAIN_DB_PATH):
        os.remove(MAIN_DB_PATH)
    os.rename(DB_BACKUP_PATH, MAIN_DB_PATH)


def _clear_db():
    """Remove main.db so Lexicon creates a fresh library on launch."""
    if os.path.islink(MAIN_DB_PATH) or os.path.exists(MAIN_DB_PATH):
        os.remove(MAIN_DB_PATH)


@pytest.fixture(scope="session")
def lexicon():
    """Session-scoped fixture that provides a Lexicon client against a clean library.

    Setup:
        1. Quits Lexicon if running
        2. Backs up the current database
        3. Removes the database so Lexicon starts fresh
        4. Launches Lexicon and waits for the API

    Teardown:
        1. Quits Lexicon
        2. Restores the original database
        3. Relaunches Lexicon
    """
    was_running = _is_api_ready()

    # Setup
    if was_running:
        _quit_lexicon()
    _backup_db()
    _clear_db()

    try:
        _launch_lexicon()
        client = Lexicon()

        # Guard: verify the library is empty before running tests
        tracks = client.tracks.list()
        if tracks and len(tracks) > 0:
            raise RuntimeError(
                f"Integration tests require an empty library, but found {len(tracks)} tracks. "
                "The database swap may have failed."
            )

        yield client
    finally:
        _quit_lexicon()
        _restore_db()
        if was_running:
            _launch_lexicon()


TEST_DIR = Path(__file__).resolve().parent


def _create_silent_wav(path: Path, duration_s: float = 8.0) -> Path:
    """Create a silent WAV file at the given path."""
    sample_rate = 48000
    channels = 1
    sample_width = 2  # 16-bit
    total_frames = int(duration_s * sample_rate)
    chunk_frames = 4096
    silence_chunk = struct.pack("<h", 0) * chunk_frames
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        frames_remaining = total_frames
        while frames_remaining > 0:
            frames = min(chunk_frames, frames_remaining)
            wf.writeframes(silence_chunk[: frames * sample_width])
            frames_remaining -= frames
    return path


@pytest.fixture(scope="session")
def create_audio_file():
    """Factory fixture that creates silent WAV files and cleans them up after."""
    created: list[Path] = []

    def _create(name: str, duration_s: float = 8.0) -> Path:
        path = TEST_DIR / name
        _create_silent_wav(path, duration_s)
        created.append(path)
        return path

    yield _create

    for path in created:
        path.unlink(missing_ok=True)
