"""Unit tests for fs_server.py — Move/Rename tool."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import pytest

from fs_server import (
    obsidian_fs_move,
    MoveNoteInput,
)


@pytest.fixture
def mock_vault(tmp_path: Path) -> Path:
    """Create a temporary vault with sample files."""
    (tmp_path / "Note.md").write_text("Content", encoding="utf-8")
    (tmp_path / "Folder").mkdir()
    (tmp_path / "Folder/SubNote.md").write_text("SubContent", encoding="utf-8")
    return tmp_path


@pytest.fixture
def mock_vault_path(mock_vault: Path) -> MagicMock:
    """Mock _vault_path to return tmp_path."""
    with patch("fs_server._vault_path", return_value=mock_vault) as m:
        yield m


class TestFsMove:
    """Tests for obsidian_fs_move tool."""

    @pytest.mark.asyncio
    async def test_rename_file(self, mock_vault: Path, mock_vault_path: MagicMock) -> None:
        """Should rename a file in the same directory."""
        params = MoveNoteInput(source="Note.md", destination="Renamed.md")
        result = await obsidian_fs_move(params)
        data = json.loads(result)
        
        assert data["status"] == "moved"
        assert not (mock_vault / "Note.md").exists()
        assert (mock_vault / "Renamed.md").exists()
        assert (mock_vault / "Renamed.md").read_text(encoding="utf-8") == "Content"

    @pytest.mark.asyncio
    async def test_move_file_new_folder(self, mock_vault: Path, mock_vault_path: MagicMock) -> None:
        """Should move file to a new folder (auto-created)."""
        params = MoveNoteInput(source="Note.md", destination="NewFolder/Moved.md")
        result = await obsidian_fs_move(params)
        data = json.loads(result)

        assert data["status"] == "moved"
        assert (mock_vault / "NewFolder").is_dir()
        assert (mock_vault / "NewFolder/Moved.md").exists()

    @pytest.mark.asyncio
    async def test_move_folder(self, mock_vault: Path, mock_vault_path: MagicMock) -> None:
        """Should move/rename a folder."""
        params = MoveNoteInput(source="Folder", destination="RenamedFolder")
        result = await obsidian_fs_move(params)
        data = json.loads(result)

        assert data["status"] == "moved"
        assert not (mock_vault / "Folder").exists()
        assert (mock_vault / "RenamedFolder").is_dir()
        assert (mock_vault / "RenamedFolder/SubNote.md").exists()

    @pytest.mark.asyncio
    async def test_move_missing_source(self, mock_vault_path: MagicMock) -> None:
        """Should return error if source does not exist."""
        params = MoveNoteInput(source="Missing.md", destination="Dest.md")
        result = await obsidian_fs_move(params)
        assert "Error: Source not found" in result

    @pytest.mark.asyncio
    async def test_move_overwrite_protection(self, mock_vault: Path, mock_vault_path: MagicMock) -> None:
        """Should fail if destination exists and overwrite=False."""
        (mock_vault / "Dest.md").write_text("Existing", encoding="utf-8")
        
        params = MoveNoteInput(source="Note.md", destination="Dest.md", overwrite=False)
        result = await obsidian_fs_move(params)
        assert "Error: Destination already exists" in result
        assert (mock_vault / "Note.md").exists()  # Source should remain

    @pytest.mark.asyncio
    async def test_move_overwrite_force(self, mock_vault: Path, mock_vault_path: MagicMock) -> None:
        """Should succeed if destination exists and overwrite=True."""
        (mock_vault / "Dest.md").write_text("Existing", encoding="utf-8")
        
        params = MoveNoteInput(source="Note.md", destination="Dest.md", overwrite=True)
        result = await obsidian_fs_move(params)
        data = json.loads(result)

        assert data["status"] == "moved"
        assert (mock_vault / "Dest.md").read_text(encoding="utf-8") == "Content"
