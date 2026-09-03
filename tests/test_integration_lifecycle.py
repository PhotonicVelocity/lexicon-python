"""Unit tests for tests/integration/lifecycle.py.

These run in the default suite on any platform: every call that would touch the
real machine (the database directory, pgrep, osascript, sleeping) is patched out.
"""

import types

import pytest

from tests.integration import lifecycle


class FakeClock:
    """Stand-in for the time module: sleeping advances the clock instantly."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def db_paths(tmp_path, monkeypatch):
    """Point the module's database constants at files under tmp_path."""
    main = tmp_path / "main.db"
    backup = tmp_path / "main.db.integration-backup"
    monkeypatch.setattr(lifecycle, "MAIN_DB_PATH", str(main))
    monkeypatch.setattr(lifecycle, "DB_BACKUP_PATH", str(backup))
    return main, backup


def _write_trio(base):
    """Create a database file and both sidecars beside it."""
    base.write_text("db")
    base.with_name(base.name + "-wal").write_text("wal")
    base.with_name(base.name + "-shm").write_text("shm")


def _sidecars(base):
    return base.with_name(base.name + "-wal"), base.with_name(base.name + "-shm")


def test_backup_moves_db_and_sidecars(db_paths):
    main, backup = db_paths
    _write_trio(main)

    lifecycle.backup_db()

    assert not main.exists()
    assert backup.read_text() == "db"
    main_wal, main_shm = _sidecars(main)
    backup_wal, backup_shm = _sidecars(backup)
    assert not main_wal.exists()
    assert not main_shm.exists()
    assert backup_wal.read_text() == "wal"
    assert backup_shm.read_text() == "shm"


def test_backup_without_sidecars(db_paths):
    main, backup = db_paths
    main.write_text("db")

    lifecycle.backup_db()

    assert not main.exists()
    assert backup.read_text() == "db"
    for path in _sidecars(backup):
        assert not path.exists()


def test_backup_missing_db_raises(db_paths):
    main, backup = db_paths

    with pytest.raises(FileNotFoundError):
        lifecycle.backup_db()

    assert not backup.exists()


def test_backup_stale_backup_raises_and_keeps_both(db_paths):
    main, backup = db_paths
    main.write_text("current")
    backup.write_text("stale")

    with pytest.raises(RuntimeError):
        lifecycle.backup_db()

    assert main.read_text() == "current"
    assert backup.read_text() == "stale"


def test_restore_replaces_fresh_db_and_sidecars(db_paths):
    main, backup = db_paths
    _write_trio(main)
    _write_trio(backup)
    backup.write_text("original")

    lifecycle.restore_db()

    assert main.read_text() == "original"
    main_wal, main_shm = _sidecars(main)
    assert main_wal.read_text() == "wal"
    assert main_shm.read_text() == "shm"
    assert not backup.exists()
    for path in _sidecars(backup):
        assert not path.exists()


def test_restore_without_backup_is_noop(db_paths):
    main, backup = db_paths
    main.write_text("current")

    lifecycle.restore_db()

    assert main.read_text() == "current"
    assert not backup.exists()


def test_clear_removes_db_and_sidecars(db_paths):
    main, _ = db_paths
    _write_trio(main)

    lifecycle.clear_db()

    assert not main.exists()
    for path in _sidecars(main):
        assert not path.exists()


def test_clear_tolerates_missing_files(db_paths):
    main, _ = db_paths

    lifecycle.clear_db()

    assert not main.exists()


def test_is_lexicon_running_uses_pgrep(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setattr(lifecycle, "subprocess", types.SimpleNamespace(run=fake_run))

    assert lifecycle.is_lexicon_running() is True
    assert calls == [["pgrep", "-x", "Lexicon"]]


def test_is_lexicon_running_false_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setattr(
        lifecycle,
        "subprocess",
        types.SimpleNamespace(
            run=lambda args, **kwargs: types.SimpleNamespace(returncode=1)
        ),
    )

    assert lifecycle.is_lexicon_running() is False


def test_is_lexicon_running_off_macos(monkeypatch):
    def fail_run(args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("subprocess.run called off macOS")

    monkeypatch.setattr(lifecycle, "IS_MACOS", False)
    monkeypatch.setattr(lifecycle, "subprocess", types.SimpleNamespace(run=fail_run))

    assert lifecycle.is_lexicon_running() is False


def test_wait_for_lexicon_exit_returns_when_process_gone(monkeypatch):
    clock = FakeClock()
    states = [True, True, False]
    monkeypatch.setattr(lifecycle, "time", clock)
    monkeypatch.setattr(lifecycle, "is_lexicon_running", lambda: states.pop(0))

    lifecycle.wait_for_lexicon_exit(120)

    assert states == []
    assert clock.slept == [lifecycle.POLL_INTERVAL, lifecycle.POLL_INTERVAL]


def test_wait_for_lexicon_exit_times_out(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(lifecycle, "time", clock)
    monkeypatch.setattr(lifecycle, "is_lexicon_running", lambda: True)

    with pytest.raises(TimeoutError) as excinfo:
        lifecycle.wait_for_lexicon_exit(5)

    assert "Quit immediately" in str(excinfo.value)
    assert clock.slept == [lifecycle.POLL_INTERVAL] * 5


def test_quit_lexicon_skips_when_not_running(monkeypatch):
    def fail_run(args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("subprocess.run called while Lexicon was not running")

    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setattr(lifecycle, "is_lexicon_running", lambda: False)
    monkeypatch.setattr(lifecycle, "subprocess", types.SimpleNamespace(run=fail_run))

    lifecycle.quit_lexicon()


def test_quit_lexicon_sends_osascript_then_waits(monkeypatch):
    calls = []
    waits = []

    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setattr(lifecycle, "is_lexicon_running", lambda: True)
    monkeypatch.setattr(
        lifecycle,
        "subprocess",
        types.SimpleNamespace(
            run=lambda args, **kwargs: (
                calls.append(args),
                types.SimpleNamespace(returncode=0, stderr=""),
            )[1]
        ),
    )
    monkeypatch.setattr(
        lifecycle, "wait_for_lexicon_exit", lambda timeout: waits.append(timeout)
    )

    lifecycle.quit_lexicon()

    assert calls == [["osascript", "-e", 'tell application "Lexicon" to quit']]
    assert waits == [lifecycle.SHUTDOWN_TIMEOUT]


def test_quit_lexicon_off_macos_prompts_and_waits_for_api(monkeypatch):
    prompts = []
    waits = []

    monkeypatch.setattr(lifecycle, "IS_MACOS", False)
    monkeypatch.setattr("builtins.input", lambda prompt="": prompts.append(prompt))
    monkeypatch.setattr(
        lifecycle,
        "wait_for_api",
        lambda ready, timeout: waits.append((ready, timeout)),
    )

    lifecycle.quit_lexicon()

    assert len(prompts) == 1
    assert waits == [(False, lifecycle.SHUTDOWN_TIMEOUT)]


def test_launch_lexicon_opens_app_and_waits_for_api(monkeypatch):
    calls = []
    waits = []

    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setattr(
        lifecycle,
        "subprocess",
        types.SimpleNamespace(
            run=lambda args, **kwargs: (
                calls.append(args),
                types.SimpleNamespace(returncode=0, stderr=""),
            )[1]
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "wait_for_api",
        lambda ready, timeout: waits.append((ready, timeout)),
    )

    lifecycle.launch_lexicon()

    assert calls == [["open", "-a", "Lexicon"]]
    assert waits == [(True, lifecycle.STARTUP_TIMEOUT)]


def test_quit_lexicon_raises_when_osascript_fails(monkeypatch):
    waits = []

    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setattr(lifecycle, "is_lexicon_running", lambda: True)
    monkeypatch.setattr(
        lifecycle,
        "subprocess",
        types.SimpleNamespace(
            run=lambda args, **kwargs: types.SimpleNamespace(
                returncode=1, stderr="execution error: Lexicon got an error (-600)\n"
            )
        ),
    )
    monkeypatch.setattr(
        lifecycle, "wait_for_lexicon_exit", lambda timeout: waits.append(timeout)
    )

    with pytest.raises(
        RuntimeError, match=r"osascript quit failed with exit 1: .*-600"
    ):
        lifecycle.quit_lexicon()
    assert waits == []


def test_launch_lexicon_raises_when_open_fails(monkeypatch):
    waits = []

    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setattr(
        lifecycle,
        "subprocess",
        types.SimpleNamespace(
            run=lambda args, **kwargs: types.SimpleNamespace(
                returncode=1, stderr="Unable to find application named 'Lexicon'\n"
            )
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "wait_for_api",
        lambda ready, timeout: waits.append((ready, timeout)),
    )

    with pytest.raises(RuntimeError, match=r"open -a Lexicon failed with exit 1"):
        lifecycle.launch_lexicon()
    assert waits == []


def test_launch_environment_drops_electron_node_mode(monkeypatch):
    monkeypatch.setenv("ELECTRON_RUN_AS_NODE", "1")
    monkeypatch.setenv("LIFECYCLE_PROBE", "kept")

    env = lifecycle._launch_environment()

    assert "ELECTRON_RUN_AS_NODE" not in env
    assert env["LIFECYCLE_PROBE"] == "kept"


def test_launch_lexicon_strips_electron_node_mode_from_open(monkeypatch):
    seen = {}

    monkeypatch.setattr(lifecycle, "IS_MACOS", True)
    monkeypatch.setenv("ELECTRON_RUN_AS_NODE", "1")
    monkeypatch.setattr(
        lifecycle,
        "subprocess",
        types.SimpleNamespace(
            run=lambda args, **kwargs: (
                seen.update(kwargs),
                types.SimpleNamespace(returncode=0, stderr=""),
            )[1]
        ),
    )
    monkeypatch.setattr(lifecycle, "wait_for_api", lambda ready, timeout: None)

    lifecycle.launch_lexicon()

    assert "ELECTRON_RUN_AS_NODE" not in seen["env"]
