"""Integration test fixtures for Lexicon API.

Provides a Lexicon client against a library emptied for the run, plus factories
for the audio files the tests add. The app and database lifecycle these fixtures
drive lives in lifecycle.py.

Note: The Lexicon local API must be enabled in Lexicon settings for tests to connect.

A watch folder configured in Lexicon is stored in Electron's Local Storage, not
in main.db, so the emptied library still imports it on launch (observed: 6265
tracks within 5 s of the API answering). The import only reads the files. The
empty-library guard below passes because the API answers before the import
lands; test_delete_track then removes every row, watch-folder rows included.
"""

import array
import math
import random
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


def _create_beat_wav(path: Path, duration_s: float = 30.0, bpm: int = 128) -> Path:
    """Create a WAV file with a synthetic drum pattern at the given tempo.

    Lexicon's beat tracker needs a chain of at least 8 detected beats from a
    steady onset stream; an 8 s file of 5 ms clicks produced no beatgrid at all.
    Every beat carries a decaying 55 Hz kick and every eighth note a short noise
    burst, which the onset detector treats like a drum loop.
    """
    sample_rate = 48000
    channels = 1
    sample_width = 2  # 16-bit
    beat_frames = int(sample_rate * 60 / bpm)
    total_frames = int(duration_s * sample_rate)

    kick_frames = int(sample_rate * 0.25)
    kick = [
        0.9
        * math.exp(-frame / (sample_rate * 0.05))
        * math.sin(2 * math.pi * 55 * frame / sample_rate)
        for frame in range(kick_frames)
    ]
    noise = random.Random(0)
    hat_frames = int(sample_rate * 0.03)
    hat = [
        0.3 * math.exp(-frame / (sample_rate * 0.008)) * noise.uniform(-1.0, 1.0)
        for frame in range(hat_frames)
    ]

    samples = [0.0] * total_frames
    for start in range(0, total_frames, beat_frames):
        for offset, value in enumerate(kick[: total_frames - start]):
            samples[start + offset] += value
    for start in range(0, total_frames, beat_frames // 2):
        for offset, value in enumerate(hat[: total_frames - start]):
            samples[start + offset] += value

    frames = array.array(
        "h", (int(max(-1.0, min(1.0, value)) * 32767) for value in samples)
    )
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(frames.tobytes())
    return path


@pytest.fixture(scope="session")
def create_beat_file():
    """Factory fixture that creates drum-pattern WAV files and cleans them up after."""
    created: list[Path] = []

    def _create(name: str, duration_s: float = 30.0, bpm: int = 128) -> Path:
        path = TEST_DIR / name
        _create_beat_wav(path, duration_s, bpm)
        created.append(path)
        return path

    yield _create

    for path in created:
        path.unlink(missing_ok=True)
