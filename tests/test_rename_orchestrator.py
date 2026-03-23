"""Tests for RenameOrchestrator (§11)."""

from onomatool.rename_orchestrator import RenameOrchestrator


def _mock_config():
    return {
        "default_provider": "mock",
        "naming_convention": "snake_case",
        "llm_model": "gpt-4o",
        "min_filename_words": 5,
        "max_filename_words": 15,
        "openai_api_key": "",
        "openai_base_url": "https://api.openai.com/v1",
        "google_api_key": "",
        "system_prompt": "",
        "user_prompt": "",
        "image_prompt": "",
        "markitdown": {"enable_plugins": False, "docintel_endpoint": ""},
    }


def test_orchestrator_dry_run(tmp_path):
    """TC-RO-001: Dry run plans rename without modifying files."""
    test_file = tmp_path / "original.txt"
    test_file.write_text("test content")

    orch = RenameOrchestrator(config=_mock_config(), dry_run=True, verbose_level=0)
    orch.process_files(str(tmp_path / "*.txt"))

    # Original file should still exist (dry run)
    assert test_file.exists()
    assert len(orch.planned_renames) == 1
    assert orch.planned_renames[0][0] == str(test_file)


def test_orchestrator_actual_rename(tmp_path):
    """TC-RO-002: Actual rename moves the file."""
    test_file = tmp_path / "original.txt"
    test_file.write_text("test content")

    orch = RenameOrchestrator(config=_mock_config(), dry_run=False, verbose_level=0)
    orch.process_files(str(tmp_path / "*.txt"))

    # Original should be gone, renamed file should exist
    assert not test_file.exists()
    renamed_files = list(tmp_path.glob("*.txt"))
    assert len(renamed_files) == 1
    assert "mock_file_one" in renamed_files[0].name


def test_orchestrator_execute_planned_renames(tmp_path):
    """TC-RO-003: Execute planned renames after dry run."""
    test_file = tmp_path / "original.txt"
    test_file.write_text("test content")

    orch = RenameOrchestrator(config=_mock_config(), dry_run=True, verbose_level=0)
    orch.process_files(str(tmp_path / "*.txt"))
    assert test_file.exists()

    # Now execute the planned renames
    orch.execute_planned_renames()
    assert not test_file.exists()
    renamed_files = list(tmp_path.glob("*.txt"))
    assert len(renamed_files) == 1


def test_orchestrator_no_files(tmp_path):
    """TC-RO-004: No matching files produces no renames."""
    orch = RenameOrchestrator(config=_mock_config(), dry_run=False, verbose_level=0)
    orch.process_files(str(tmp_path / "*.nonexistent"))
    assert len(orch.planned_renames) == 0


def test_orchestrator_multiple_files(tmp_path):
    """TC-RO-005: Multiple files are all processed."""
    for name in ["a.txt", "b.txt", "c.txt"]:
        (tmp_path / name).write_text(f"content of {name}")

    orch = RenameOrchestrator(config=_mock_config(), dry_run=True, verbose_level=0)
    orch.process_files(str(tmp_path / "*.txt"))
    assert len(orch.planned_renames) == 3
