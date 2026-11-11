"""Lexicon app and database lifecycle used by the integration fixtures.

The fixtures in conftest.py drive Lexicon through these functions: quitting and
launching the app, and swapping main.db for an empty library. This module is
import-safe on every platform and never calls pytest.skip, so its unit tests in
tests/test_integration_lifecycle.py run in CI where Lexicon does not exist.
"""

import os
import platform
import subprocess
import time

import requests

from lexicon import LEXICON_PORT, DEFAULT_HOST

IS_MACOS = platform.system() == "Darwin"

IS_WINDOWS = platform.system() == "Windows"

if IS_MACOS:
    LEXICON_DATA_DIR = os.path.expanduser("~/Library/Application Support/lexicon")
elif IS_WINDOWS:
    LEXICON_DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), "Lexicon")
else:
    # Empty when unset. conftest.py turns that into a module-level skip; this
    # module stays importable so its unit tests can run anywhere.
    LEXICON_DATA_DIR = os.environ.get("LEXICON_DATA_DIR", "")

MAIN_DB_PATH = os.path.join(LEXICON_DATA_DIR, "main.db")
DB_BACKUP_PATH = os.path.join(LEXICON_DATA_DIR, "main.db.integration-backup")
API_URL = f"http://{DEFAULT_HOST}:{LEXICON_PORT}/v1/tracks"
LEXICON_APP_NAME = "Lexicon"

# Startup to API ready measured 4.6 s against a full library.
STARTUP_TIMEOUT = 60
# Quitting runs the "Closing Lexicon..." loader, which closes and checkpoints the database
# and can also write the daily backup zip of the library (about 200 MB), so allow minutes.
SHUTDOWN_TIMEOUT = 120
POLL_INTERVAL = 1

# SQLite locates the write-ahead log and shared-memory files by appending these
# suffixes to the database filename, so they have to move with main.db.
DB_SIDECAR_SUFFIXES = ("-wal", "-shm")


# Lexicon v1.12 holds a request from an app the user has not answered for while it
# shows an approval popup, so a plain probe would time out against a running app.
# A request with an Origin header counts as coming from a web page: v1.12 answers it
# at once with HTTP 401 and error code 9 and never shows the popup, and v1.11 and
# older ignore the header.
_PROBE_HEADERS = {"Origin": "http://localhost"}


def is_api_ready() -> bool:
    """Check if the Lexicon API is answering HTTP requests.

    Any HTTP response counts, including v1.12's 401 for the probe, because the
    question is whether the server is up, not whether this probe is let in.
    """
    try:
        requests.get(API_URL, headers=_PROBE_HEADERS, timeout=2)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


def wait_for_api(ready: bool, timeout: int):
    """Poll until the API matches the expected state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_api_ready() == ready:
            return
        time.sleep(POLL_INTERVAL)
    if ready:
        raise TimeoutError(
            "Lexicon API did not become ready in time. "
            "Make sure the local API is enabled in Lexicon settings."
        )
    raise TimeoutError(
        "Lexicon did not shut down in time. Please close it manually and re-run."
    )


def is_lexicon_running() -> bool:
    """Check whether the main Lexicon process is alive.

    Only macOS has a process check; the other platforms drive the app by prompt.
    """
    if not IS_MACOS:
        return False
    # Helper processes are named "Lexicon Helper ...", so -x matches the main process only.
    result = subprocess.run(["pgrep", "-x", LEXICON_APP_NAME], capture_output=True)
    return result.returncode == 0


def wait_for_lexicon_exit(timeout: int):
    """Poll until the Lexicon process is gone."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_lexicon_running():
            return
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f"Lexicon was still running {timeout}s after the quit request. It is probably "
        'showing the "Closing Lexicon..." loader; press its "Quit immediately" button, '
        "or wait for the exit work to finish and re-run."
    )


# Electron reads this variable and, when it is set, runs as plain Node instead of
# starting the app: with no script and a closed stdin it exits 0 within a second,
# before the app writes a log line. Shells hosted by an Electron app (the VS Code
# extension host, for one) carry it, and `open` forwards the caller's environment
# to the launched app, so it has to be stripped before launching Lexicon.
_ELECTRON_NODE_MODE_VARIABLE = "ELECTRON_RUN_AS_NODE"


def _launch_environment() -> dict[str, str]:
    """Return the current environment without the Electron node-mode variable."""
    return {
        name: value
        for name, value in os.environ.items()
        if name != _ELECTRON_NODE_MODE_VARIABLE
    }


def _run_checked(args: list[str], what: str, env: dict[str, str] | None = None) -> None:
    """Run a command and raise with its stderr when it exits non-zero.

    `open` and `osascript` report a failed launch or AppleScript error only through
    the exit status; a swallowed failure shows up later as a misleading API timeout.
    """
    result = subprocess.run(args, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            f"{what} failed with exit {result.returncode}: {result.stderr.strip()}"
        )


def quit_lexicon():
    """Quit Lexicon and wait for the process to exit. Prompts off macOS.

    The API stops answering in Lexicon's before-quit handler, while the database
    close and checkpoint run after it, so process exit is what says the database
    files are free.
    """
    if IS_MACOS:
        # Nothing to quit when the process is absent, and AppleScript sent to an
        # app that is not running can launch it.
        if not is_lexicon_running():
            return
        _run_checked(
            ["osascript", "-e", f'tell application "{LEXICON_APP_NAME}" to quit'],
            "osascript quit",
        )
        wait_for_lexicon_exit(SHUTDOWN_TIMEOUT)
        return

    input("Please quit Lexicon, then press Enter...")
    wait_for_api(ready=False, timeout=SHUTDOWN_TIMEOUT)


def launch_lexicon():
    """Launch Lexicon. Uses `open` on macOS, prompts otherwise."""
    if IS_MACOS:
        _run_checked(
            ["open", "-a", LEXICON_APP_NAME],
            f"open -a {LEXICON_APP_NAME}",
            env=_launch_environment(),
        )
    else:
        input("Please launch Lexicon, then press Enter...")
    wait_for_api(ready=True, timeout=STARTUP_TIMEOUT)


def _path_present(path: str) -> bool:
    """Report whether a path exists, counting a broken symlink as present."""
    return os.path.islink(path) or os.path.exists(path)


def _db_file_paths(base: str) -> tuple[str, ...]:
    """Return a database path followed by its sidecar paths."""
    return (base, *(base + suffix for suffix in DB_SIDECAR_SUFFIXES))


def backup_db():
    """Move the current main.db and its sidecars aside.

    A stray WAL left at the database path would be applied to whichever database
    sits there next, so the sidecars move with main.db.
    """
    if not _path_present(MAIN_DB_PATH):
        raise FileNotFoundError(f"No database found at {MAIN_DB_PATH}")
    if _path_present(DB_BACKUP_PATH):
        raise RuntimeError(
            f"A backup from an earlier run is already at {DB_BACKUP_PATH}. "
            "os.rename would replace it and lose the original library. Inspect it, "
            "then move or delete it before running the integration tests again."
        )

    for source, target in zip(
        _db_file_paths(MAIN_DB_PATH), _db_file_paths(DB_BACKUP_PATH)
    ):
        if _path_present(source):
            os.rename(source, target)


def restore_db():
    """Restore the original main.db and its sidecars from the backup.

    Restoring the database without its WAL would drop the writes still in it.
    """
    if not _path_present(DB_BACKUP_PATH):
        return

    clear_db()
    for source, target in zip(
        _db_file_paths(DB_BACKUP_PATH), _db_file_paths(MAIN_DB_PATH)
    ):
        if _path_present(source):
            os.rename(source, target)


def clear_db():
    """Remove main.db and its sidecars so Lexicon creates a fresh library on launch."""
    for path in _db_file_paths(MAIN_DB_PATH):
        if _path_present(path):
            os.remove(path)
