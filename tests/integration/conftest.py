"""Integration test fixtures for Lexicon API.

Provides a Lexicon client against a library emptied for the run, plus factories
for the audio files the tests add. The app and database lifecycle these fixtures
drive lives in lifecycle.py.

Note: The Lexicon local API must be enabled in Lexicon settings for tests to connect.
"""

import math
import struct
import wave
from pathlib import Path

import pytest

from lexicon import Lexicon

from . import lifecycle
from .lifecycle import (
    IS_MACOS,
    IS_WINDOWS,
    backup_db,
    clear_db,
    is_api_ready,
    launch_lexicon,
    quit_lexicon,
    restore_db,
)

if not IS_MACOS and not IS_WINDOWS and lifecycle.LEXICON_DATA_DIR == "":
    pytest.skip(
        "Set LEXICON_DATA_DIR environment variable to the Lexicon data directory",
        allow_module_level=True,
    )


@pytest.fixture(scope="session")
def lexicon():
    """Session-scoped fixture that provides a Lexicon client against a clean library.

    If Lexicon is already running with an empty library, uses it as-is
    and skips the db swap (useful for iterating on tests).

    Otherwise:
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
    swapped = False

    # Check if already running with an empty library. Lexicon() verifies the
    # connection on construction, so it is only built once the API answers.
    if is_api_ready():
        client = Lexicon()
        tracks = client.tracks.list()
        if not tracks or len(tracks) == 0:
            yield client
            return

    # Need to swap — library is populated or Lexicon isn't running
    was_running = is_api_ready()
    if was_running:
        quit_lexicon()
    backup_db()
    clear_db()
    swapped = True

    try:
        launch_lexicon()
        client = Lexicon()

        # Guard: verify the library is empty
        tracks = client.tracks.list()
        if tracks and len(tracks) > 0:
            raise RuntimeError(
                f"Integration tests require an empty library, but found {len(tracks)} tracks. "
                "The database swap may have failed."
            )

        yield client
    finally:
        if swapped:
            quit_lexicon()
            restore_db()
            if was_running:
                launch_lexicon()


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


def _create_click_wav(path: Path, duration_s: float = 8.0, bpm: int = 120) -> Path:
    """Create a WAV file with one click per beat at the given tempo.

    Lexicon's beatgrid analyzer needs transients; a silent file yields no
    tempomarkers. Each click is a 5 ms full-scale 1 kHz burst with a linear
    decay, followed by silence until the next beat.
    """
    sample_rate = 48000
    channels = 1
    sample_width = 2  # 16-bit
    click_ms = 5
    click_hz = 1000
    peak = 32767
    click_frames = int(sample_rate * click_ms / 1000)
    beat_frames = int(sample_rate * 60 / bpm)
    total_frames = int(duration_s * sample_rate)

    click = b"".join(
        struct.pack(
            "<h",
            int(
                peak
                * (1.0 - frame / click_frames)
                * math.sin(2 * math.pi * click_hz * frame / sample_rate)
            ),
        )
        for frame in range(click_frames)
    )
    beat = click + struct.pack("<h", 0) * (beat_frames - click_frames)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        frames_written = 0
        while frames_written < total_frames:
            frames = min(beat_frames, total_frames - frames_written)
            wf.writeframes(beat[: frames * sample_width])
            frames_written += frames
    return path


@pytest.fixture(scope="session")
def create_click_file():
    """Factory fixture that creates click-track WAV files and cleans them up after."""
    created: list[Path] = []

    def _create(name: str, duration_s: float = 8.0, bpm: int = 120) -> Path:
        path = TEST_DIR / name
        _create_click_wav(path, duration_s, bpm)
        created.append(path)
        return path

    yield _create

    for path in created:
        path.unlink(missing_ok=True)
