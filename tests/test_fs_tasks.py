"""Unit tests for fs_server.py — Tasks support."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from fs_server import (
    obsidian_fs_tasks_list,
    obsidian_fs_task_toggle,
    FsTasksListInput,
    FsTaskToggleInput,
    _vault_path,
)


@pytest.fixture
def mock_vault(tmp_path: Path) -> Path:
    """Create a temporary vault with sample notes."""
    # Note 1: Mixed tasks
    (tmp_path / "Project.md").write_text(
        "# Project\n\n- [ ] Task 1\n- [x] Task 2\n- [ ] Task 3\nNot a task\n",
        encoding="utf-8"
    )
    # Note 2: Todo only
    (tmp_path / "Todo.md").write_text(
        "- [ ] Buy milk\n- [ ] Call Bob\n",
        encoding="utf-8"
    )
    # Note 3: Subfolder
    sub = tmp_path / "Work"
    sub.mkdir()
    (sub / "Meeting.md").write_text(
        "- [x] Prepare slides\n",
        encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def mock_vault_path(mock_vault: Path) -> MagicMock:
    """Mock _vault_path to return tmp_path."""
    with patch("fs_server._vault_path", return_value=mock_vault) as m:
        yield m


class TestFsTasksList:
    """Tests for obsidian_fs_tasks_list tool."""

    @pytest.mark.asyncio
    async def test_list_all(self, mock_vault_path: MagicMock) -> None:
        """Should list all 5 tasks from all files."""
        result = await obsidian_fs_tasks_list(FsTasksListInput())
        assert "- [ ] Task 1 (Project.md:3)" in result
        assert "- [x] Task 2 (Project.md:4)" in result
        assert "- [ ] Buy milk (Todo.md:1)" in result
        assert "- [x] Prepare slides (Work/Meeting.md:1)" in result
        assert "6 tasks found" in result

    @pytest.mark.asyncio
    async def test_filter_todo(self, mock_vault_path: MagicMock) -> None:
        """Should list only incomplete tasks."""
        result = await obsidian_fs_tasks_list(FsTasksListInput(todo=True))
        assert "Task 1" in result
        assert "Task 2" not in result
        assert "Buy milk" in result

    @pytest.mark.asyncio
    async def test_filter_done(self, mock_vault_path: MagicMock) -> None:
        """Should list only completed tasks."""
        result = await obsidian_fs_tasks_list(FsTasksListInput(done=True))
        assert "Task 1" not in result
        assert "Task 2" in result

    @pytest.mark.asyncio
    async def test_filter_folder(self, mock_vault_path: MagicMock) -> None:
        """Should list tasks only in specified folder."""
        result = await obsidian_fs_tasks_list(FsTasksListInput(folder="Work"))
        assert "Prepare slides" in result
        assert "Task 1" not in result


class TestFsTaskToggle:
    """Tests for obsidian_fs_task_toggle tool."""

    @pytest.mark.asyncio
    async def test_toggle_todo_to_done(self, mock_vault: Path, mock_vault_path: MagicMock) -> None:
        """Should toggle [ ] to [x]."""
        params = FsTaskToggleInput(path="Project.md", line=3)
        result = await obsidian_fs_task_toggle(params)
        assert "Toggled task at Project.md:3 to [x]" in result
        
        content = (mock_vault / "Project.md").read_text(encoding="utf-8")
        assert "- [x] Task 1" in content

    @pytest.mark.asyncio
    async def test_toggle_done_to_todo(self, mock_vault: Path, mock_vault_path: MagicMock) -> None:
        """Should toggle [x] to [ ]."""
        params = FsTaskToggleInput(path="Project.md", line=4)
        result = await obsidian_fs_task_toggle(params)
        assert "Toggled task at Project.md:4 to [ ]" in result

        content = (mock_vault / "Project.md").read_text(encoding="utf-8")
        assert "- [ ] Task 2" in content

    @pytest.mark.asyncio
    async def test_toggle_invalid_line(self, mock_vault_path: MagicMock) -> None:
        """Should return error if line is not a task."""
        params = FsTaskToggleInput(path="Project.md", line=1)  # Heading line
        result = await obsidian_fs_task_toggle(params)
        assert "Error: Line 1 in Project.md is not a task" in result

    @pytest.mark.asyncio
    async def test_toggle_not_found(self, mock_vault_path: MagicMock) -> None:
        """Should return error if file not found."""
        params = FsTaskToggleInput(path="NonExistent.md", line=1)
        result = await obsidian_fs_task_toggle(params)
        assert "Error: Note not found" in result
