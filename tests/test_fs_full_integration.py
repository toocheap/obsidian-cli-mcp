
import pytest
import json
import os
from pathlib import Path
from datetime import datetime
from fs_server import (
    obsidian_fs_create, obsidian_fs_read, obsidian_fs_edit, obsidian_fs_delete,
    obsidian_fs_list_folder, obsidian_fs_get_tags, obsidian_fs_get_backlinks,
    obsidian_fs_daily_note,
    CreateNoteInput, ReadNoteInput, EditNoteInput, DeleteNoteInput,
    ListFolderInput, GetTagsInput, GetBacklinksInput, CreateDailyNoteInput
)

@pytest.fixture
def vault_dir(tmp_path, monkeypatch):
    """Create a temporary vault directory."""
    vault = tmp_path / "test_vault"
    vault.mkdir()
    
    # Use monkeypatch for safe environment variable handling
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    
    # Clear cache to ensure fs_server picks up the new env var
    from fs_server import _vault_path
    _vault_path.cache_clear()
    
    return vault

@pytest.mark.asyncio
class TestFsCreate:
    async def test_create_new_note(self, vault_dir):
        res = await obsidian_fs_create(CreateNoteInput(path="New.md", content="# New"))
        data = json.loads(res)
        assert data["status"] == "created"
        assert (vault_dir / "New.md").read_text() == "# New"

    async def test_create_existing_fail(self, vault_dir):
        (vault_dir / "Exists.md").write_text("Old")
        res = await obsidian_fs_create(CreateNoteInput(path="Exists.md", content="New"))
        assert "Error: Note already exists" in res
        assert (vault_dir / "Exists.md").read_text() == "Old"

    async def test_create_overwrite(self, vault_dir):
        (vault_dir / "Overwrite.md").write_text("Old")
        res = await obsidian_fs_create(CreateNoteInput(path="Overwrite.md", content="New", overwrite=True))
        assert "created" in res
        assert (vault_dir / "Overwrite.md").read_text() == "New"
        
    async def test_create_nested_folder(self, vault_dir):
        res = await obsidian_fs_create(CreateNoteInput(path="Folder/Nested/Note.md", content="Content"))
        assert "created" in res
        assert (vault_dir / "Folder/Nested/Note.md").exists()

@pytest.mark.asyncio
class TestFsRead:
    async def test_read_success(self, vault_dir):
        (vault_dir / "Read.md").write_text("# Content")
        res = await obsidian_fs_read(ReadNoteInput(path="Read.md"))
        data = json.loads(res)
        assert data["content"] == "# Content"
        assert data["name"] == "Read"
        
    async def test_read_missing(self, vault_dir):
        res = await obsidian_fs_read(ReadNoteInput(path="Missing.md"))
        assert "Error: Note not found" in res

@pytest.mark.asyncio
class TestFsEdit:
    async def test_append(self, vault_dir):
        (vault_dir / "Append.md").write_text("Line 1")
        res = await obsidian_fs_edit(EditNoteInput(path="Append.md", operation="append", content="Line 2"))
        assert "edited" in res
        assert (vault_dir / "Append.md").read_text() == "Line 1\nLine 2"

    async def test_replace(self, vault_dir):
        (vault_dir / "Replace.md").write_text("Hello World")
        res = await obsidian_fs_edit(EditNoteInput(path="Replace.md", operation="replace", find="World", content="Python"))
        assert "edited" in res
        assert (vault_dir / "Replace.md").read_text() == "Hello Python"

    async def test_replace_not_found(self, vault_dir):
        (vault_dir / "ReplaceFail.md").write_text("Hello World")
        res = await obsidian_fs_edit(EditNoteInput(path="ReplaceFail.md", operation="replace", find="Universe", content="Python"))
        assert "Error: Text to replace not found" in res

@pytest.mark.asyncio
class TestFsDelete:
    async def test_delete_success(self, vault_dir):
        (vault_dir / "Delete.md").write_text("Content")
        res = await obsidian_fs_delete(DeleteNoteInput(path="Delete.md", confirm=True))
        assert "deleted" in res
        assert not (vault_dir / "Delete.md").exists()

    async def test_delete_no_confirm(self, vault_dir):
        (vault_dir / "Safe.md").write_text("Content")
        res = await obsidian_fs_delete(DeleteNoteInput(path="Safe.md", confirm=False))
        assert "Error: Deletion not confirmed" in res
        assert (vault_dir / "Safe.md").exists()

@pytest.mark.asyncio
class TestFsListFolder:
    async def test_list_recursive(self, vault_dir):
        (vault_dir / "A.md").touch()
        (vault_dir / "Folder").mkdir()
        (vault_dir / "Folder/B.md").touch()
        
        res = await obsidian_fs_list_folder(ListFolderInput())
        assert "A" in res
        assert "Folder" in res
        assert "B" in res

@pytest.mark.asyncio
class TestFsTags:
    async def test_get_tags(self, vault_dir):
        (vault_dir / "Note1.md").write_text("#tag1 #tag2")
        (vault_dir / "Note2.md").write_text("#tag1")
        
        res = await obsidian_fs_get_tags(GetTagsInput())
        assert "#tag1 (2 notes)" in res
        assert "#tag2 (1 notes)" in res

@pytest.mark.asyncio
class TestFsBacklinks:
    async def test_get_backlinks(self, vault_dir):
        (vault_dir / "Target.md").touch()
        (vault_dir / "Source.md").write_text("Link to [[Target]]")
        
        res = await obsidian_fs_get_backlinks(GetBacklinksInput(note_name="Target"))
        assert "Source" in res

@pytest.mark.asyncio
class TestFsDailyNote:
    async def test_create_daily_default(self, vault_dir):
        res = await obsidian_fs_daily_note(CreateDailyNoteInput())
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in res
        assert (vault_dir / f"{today}.md").exists()
        
    async def test_create_daily_template(self, vault_dir):
        (vault_dir / "Template.md").write_text("Daily Note: {{date}}")
        res = await obsidian_fs_daily_note(CreateDailyNoteInput(date="2099-01-01", template="Template.md"))
        assert "created" in res
        content = (vault_dir / "2099-01-01.md").read_text()
        assert "Daily Note: 2099-01-01" in content

