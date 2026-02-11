"""Unit tests for fs_server.py — Frontmatter parsing."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import pytest

from fs_server import (
    obsidian_fs_read,
    obsidian_fs_search,
    ReadNoteInput,
    SearchNotesInput,
    ResponseFormat,
)

try:
    import frontmatter
except ImportError:
    frontmatter = None


@pytest.fixture
def mock_vault(tmp_path: Path) -> Path:
    """Create a temporary vault with frontmatter notes."""
    # Note 1: Full frontmatter
    (tmp_path / "Full.md").write_text(
        "---\n"
        "aliases: [MyAlias]\n"
        "tags: [tag1, tag2]\n"
        "priority: 1\n"
        "---\n"
        "# Content\nThis is content.",
        encoding="utf-8"
    )
    # Note 2: No frontmatter
    (tmp_path / "None.md").write_text(
        "# Just Content\nNo frontmatter here.",
        encoding="utf-8"
    )
    # Note 3: Invalid frontmatter (should be handled gracefully)
    (tmp_path / "Invalid.md").write_text(
        "---\n"
        "broken: [ unclosed list\n"
        "---\n"
        "Content",
        encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def mock_vault_path(mock_vault: Path) -> MagicMock:
    """Mock _vault_path to return tmp_path."""
    with patch("fs_server._vault_path", return_value=mock_vault) as m:
        yield m


class TestFrontmatterRead:
    """Tests for obsidian_fs_read with frontmatter."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(frontmatter is None, reason="python-frontmatter not installed")
    async def test_read_frontmatter(self, mock_vault_path: MagicMock) -> None:
        """Should parse aliases, tags, and custom fields."""
        result_json = await obsidian_fs_read(ReadNoteInput(path="Full.md"))
        data = json.loads(result_json)
        
        assert "frontmatter" in data
        fm = data["frontmatter"]
        assert fm["aliases"] == ["MyAlias"]
        assert fm["priority"] == 1
        assert "tag1" in fm["tags"]
        
        # Tags should be merged in top-level tags list too
        assert "tag1" in data["tags"]
        assert "tag2" in data["tags"]

    @pytest.mark.asyncio
    async def test_read_no_frontmatter(self, mock_vault_path: MagicMock) -> None:
        """Should return empty frontmatter dict."""
        result_json = await obsidian_fs_read(ReadNoteInput(path="None.md"))
        data = json.loads(result_json)
        
        assert data["frontmatter"] == {}

    @pytest.mark.asyncio
    async def test_read_invalid_frontmatter(self, mock_vault_path: MagicMock) -> None:
        """Should handle invalid YAML gracefully (treat as content or empty FM)."""
        # python-frontmatter often keeps raw content if parsing fails, or throws error
        # fs_server should catch and fallback.
        try:
            result_json = await obsidian_fs_read(ReadNoteInput(path="Invalid.md"))
            data = json.loads(result_json)
            # Either empty FM or parsing error logic
            assert isinstance(data.get("frontmatter", {}), dict)
        except Exception:
            pytest.fail("Should not raise exception on invalid frontmatter")


class TestFrontmatterSearch:
    """Tests for search inclusion of frontmatter."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(frontmatter is None, reason="python-frontmatter not installed")
    async def test_search_returns_frontmatter(self, mock_vault_path: MagicMock) -> None:
        """Search results should include frontmatter in metadata."""
        params = SearchNotesInput(query="Content", response_format=ResponseFormat.JSON)
        result_json = await obsidian_fs_search(params)
        data = json.loads(result_json)
        
        full_note = next(r for r in data["results"] if r["name"] == "Full")
        assert "frontmatter" in full_note
        assert full_note["frontmatter"]["aliases"] == ["MyAlias"]
