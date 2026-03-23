"""Tests for the undo/history system (RenameHistory and CLI integration)."""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from onomatool.cli import main
from onomatool.history import RenameHistory


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database path for testing."""
    db_path = tmp_path / "test_history.db"
    return str(db_path)


@pytest.fixture
def history(temp_db):
    """Create a RenameHistory instance with temp database."""
    h = RenameHistory(db_path=temp_db)
    yield h
    h.close()


# TC-UNDO-001: Session creation and rename recording
def test_session_creation_and_recording(history, temp_db):
    """Create session, record rename, verify in DB."""
    session_id = history.create_session("/test/dir")
    assert session_id > 0

    history.record_rename(session_id, "/test/old.txt", "/test/new.txt", status="ok")

    # Verify in database
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row

    session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    assert session is not None
    assert session["working_dir"] == "/test/dir"
    assert session["file_count"] == 1

    renames = conn.execute("SELECT * FROM renames WHERE session_id = ?", (session_id,)).fetchall()
    assert len(renames) == 1
    assert renames[0]["original_path"] == "/test/old.txt"
    assert renames[0]["new_path"] == "/test/new.txt"
    assert renames[0]["status"] == "ok"

    conn.close()


# TC-UNDO-002: --undo reverses most recent session
def test_undo_reverses_recent_session(tmp_path, temp_db):
    """Create file, rename, undo, verify original restored."""
    # Create original file
    original = tmp_path / "original.txt"
    original.write_text("test content")
    renamed = tmp_path / "renamed.txt"

    # Simulate rename
    os.rename(str(original), str(renamed))
    assert not original.exists()
    assert renamed.exists()

    # Record in history
    history = RenameHistory(db_path=temp_db)
    session_id = history.create_session(str(tmp_path))
    history.record_rename(session_id, str(original), str(renamed))

    # Undo
    results = history.undo_session()
    history.close()

    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert original.exists()
    assert not renamed.exists()
    assert original.read_text() == "test content"


# TC-UNDO-003: --undo with session ID
def test_undo_specific_session(tmp_path, temp_db):
    """Create 2 sessions, undo specific one."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    renamed1 = tmp_path / "renamed1.txt"
    renamed2 = tmp_path / "renamed2.txt"

    file1.write_text("content1")
    file2.write_text("content2")

    history = RenameHistory(db_path=temp_db)

    # Session 1
    session1_id = history.create_session(str(tmp_path))
    os.rename(str(file1), str(renamed1))
    history.record_rename(session1_id, str(file1), str(renamed1))

    # Session 2
    session2_id = history.create_session(str(tmp_path))
    os.rename(str(file2), str(renamed2))
    history.record_rename(session2_id, str(file2), str(renamed2))

    # Undo session 1 specifically
    results = history.undo_session(session1_id)
    history.close()

    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert file1.exists()  # Session 1 undone
    assert not renamed1.exists()
    assert renamed2.exists()  # Session 2 untouched
    assert not file2.exists()


# TC-UNDO-005: Undo warns if file missing
def test_undo_warns_if_file_missing(tmp_path, temp_db):
    """Rename, delete target, undo returns warning."""
    original = tmp_path / "original.txt"
    renamed = tmp_path / "renamed.txt"

    original.write_text("content")
    os.rename(str(original), str(renamed))

    history = RenameHistory(db_path=temp_db)
    session_id = history.create_session(str(tmp_path))
    history.record_rename(session_id, str(original), str(renamed))

    # Delete the renamed file
    renamed.unlink()

    # Undo should warn
    results = history.undo_session()
    history.close()

    assert len(results) == 1
    assert results[0]["status"] == "warning"
    assert "not found" in results[0]["message"].lower()


# TC-UNDO-006: --history lists sessions
def test_history_lists_sessions(temp_db, capsys):
    """Create 3 sessions, verify output format."""
    history = RenameHistory(db_path=temp_db)

    # Create 3 sessions
    for i in range(3):
        session_id = history.create_session(f"/test/dir{i}")
        history.record_rename(session_id, f"/test/old{i}.txt", f"/test/new{i}.txt")

    history.close()

    # Test via CLI
    from onomatool.cli import _handle_history
    import onomatool.history

    # Monkey-patch DEFAULT_DB_PATH
    original_path = onomatool.history.DEFAULT_DB_PATH
    onomatool.history.DEFAULT_DB_PATH = temp_db

    try:
        result = _handle_history()
        captured = capsys.readouterr()

        assert result == 0
        assert "ID" in captured.out
        assert "Timestamp" in captured.out
        assert "Files" in captured.out
        assert "Directory" in captured.out
        assert "/test/dir0" in captured.out
        assert "/test/dir1" in captured.out
        assert "/test/dir2" in captured.out
    finally:
        onomatool.history.DEFAULT_DB_PATH = original_path


# TC-UNDO-007: Empty database
def test_undo_with_no_sessions(temp_db):
    """Undo with no sessions returns error message."""
    history = RenameHistory(db_path=temp_db)
    results = history.undo_session()
    history.close()

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "No sessions found" in results[0]["message"]


# TC-UNDO-008: Auto-prune removes old sessions
def test_auto_prune_old_sessions(temp_db):
    """Insert old timestamp, prune, verify removed."""
    history = RenameHistory(db_path=temp_db)

    # Create old session manually
    old_timestamp = (datetime.now() - timedelta(days=100)).isoformat()
    conn = history._connect()
    cursor = conn.execute(
        "INSERT INTO sessions (timestamp, working_dir, file_count) VALUES (?, ?, ?)",
        (old_timestamp, "/test", 1)
    )
    old_session_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO renames (session_id, original_path, new_path, timestamp, status) VALUES (?, ?, ?, ?, ?)",
        (old_session_id, "/old.txt", "/new.txt", old_timestamp, "ok")
    )
    conn.commit()

    # Create recent session
    recent_session_id = history.create_session("/test/recent")
    history.record_rename(recent_session_id, "/recent_old.txt", "/recent_new.txt")

    # Prune with 90-day retention
    pruned_count = history.prune(retention_days=90)

    assert pruned_count == 1

    # Verify old session removed
    sessions = history.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["id"] == recent_session_id

    history.close()


# TC-UNDO-010: Failed files recorded with error status
def test_failed_files_error_status(temp_db):
    """Check status='error' recording."""
    history = RenameHistory(db_path=temp_db)

    session_id = history.create_session("/test")
    history.record_rename(session_id, "/old.txt", "/new.txt", status="error")

    renames = history.get_session_renames(session_id)
    assert len(renames) == 1
    assert renames[0]["status"] == "error"

    history.close()


# Additional edge cases
def test_undo_with_existing_original(tmp_path, temp_db):
    """Undo fails if original filename already exists."""
    original = tmp_path / "original.txt"
    renamed = tmp_path / "renamed.txt"

    original.write_text("original content")
    os.rename(str(original), str(renamed))

    history = RenameHistory(db_path=temp_db)
    session_id = history.create_session(str(tmp_path))
    history.record_rename(session_id, str(original), str(renamed))

    # Create a new file with the original name
    original.write_text("new content")

    results = history.undo_session()
    history.close()

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "already exists" in results[0]["message"]


def test_multiple_renames_in_session(tmp_path, temp_db):
    """Undo multiple renames in reverse order."""
    files = []
    renamed = []

    for i in range(3):
        f = tmp_path / f"file{i}.txt"
        f.write_text(f"content{i}")
        files.append(f)

        r = tmp_path / f"renamed{i}.txt"
        os.rename(str(f), str(r))
        renamed.append(r)

    history = RenameHistory(db_path=temp_db)
    session_id = history.create_session(str(tmp_path))

    for i in range(3):
        history.record_rename(session_id, str(files[i]), str(renamed[i]))

    results = history.undo_session()
    history.close()

    assert len(results) == 3
    for result in results:
        assert result["status"] == "ok"

    # All originals restored
    for f in files:
        assert f.exists()

    # All renamed files gone
    for r in renamed:
        assert not r.exists()


def test_get_latest_session_id_empty(temp_db):
    """get_latest_session_id returns None when empty."""
    history = RenameHistory(db_path=temp_db)
    assert history.get_latest_session_id() is None
    history.close()


def test_list_sessions_respects_limit(temp_db):
    """list_sessions respects the limit parameter."""
    history = RenameHistory(db_path=temp_db)

    # Create 25 sessions
    for i in range(25):
        history.create_session(f"/test/dir{i}")

    sessions = history.list_sessions(limit=10)
    assert len(sessions) == 10

    # Should be in reverse order (most recent first)
    assert sessions[0]["id"] > sessions[9]["id"]

    history.close()
