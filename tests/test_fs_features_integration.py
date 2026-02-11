
import pytest
import shutil
import json
import os
import sys
from pathlib import Path
from fs_server import (
    obsidian_fs_create, obsidian_fs_edit, obsidian_fs_read, obsidian_fs_property,
    CreateNoteInput, EditNoteInput, ReadNoteInput, PropertyInput
)

# Integration tests using real filesystem (no mocks)

@pytest.fixture
def vault_dir(tmp_path, monkeypatch):
    """Create a temporary vault directory."""
    vault = tmp_path / "test_vault"
    vault.mkdir()
    
    # Use monkeypatch for safe environment variable handling
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    
    # Clear cache to pick up new env var (since fs_server caches it)
    from fs_server import _vault_path
    _vault_path.cache_clear()
    
    yield vault
    # Cleanup done by tmp_path, but environment var reset might be needed if running in same process
    # However, for pytest it's usually fine. We can unset it if strict.

@pytest.mark.asyncio
async def test_prepend_with_frontmatter(vault_dir):
    """Test prepending content to a note with frontmatter."""
    # 1. Create note
    content = """---
title: Original
---
Body text."""
    await obsidian_fs_create(CreateNoteInput(path="PrependFM.md", content=content))
    
    # 2. Prepend
    await obsidian_fs_edit(EditNoteInput(path="PrependFM.md", operation="prepend", content="Prepended line"))
    
    # 3. Verify
    note_path = vault_dir / "PrependFM.md"
    new_content = note_path.read_text()
    
    expected = """---
title: Original
---
Prepended line
Body text."""
    assert new_content.strip() == expected.strip()

@pytest.mark.asyncio
async def test_prepend_without_frontmatter(vault_dir):
    """Test prepending content to a note without frontmatter."""
    # 1. Create note
    await obsidian_fs_create(CreateNoteInput(path="Plain.md", content="Body text."))
    
    # 2. Prepend
    await obsidian_fs_edit(EditNoteInput(path="Plain.md", operation="prepend", content="Prepended line"))
    
    # 3. Verify
    note_path = vault_dir / "Plain.md"
    new_content = note_path.read_text()
    
    expected = """Prepended line
Body text."""
    assert new_content.strip() == expected.strip()

@pytest.mark.asyncio
async def test_properties_lifecycle(vault_dir):
    """Test setting, getting, listing, and removing properties."""
    # 1. Create note
    await obsidian_fs_create(CreateNoteInput(path="Props.md", content="# Hello"))
    
    # 2. Set property
    res = await obsidian_fs_property(PropertyInput(path="Props.md", operation="set", key="test_key", value="test_value"))
    
    if "python-frontmatter not installed" in res:
        pytest.skip("python-frontmatter not installed; skipping property test")

    assert '"status": "set"' in res
    
    # 3. Get property
    res = await obsidian_fs_property(PropertyInput(path="Props.md", operation="get", key="test_key"))
    data = json.loads(res)
    assert data["test_key"] == "test_value"
    
    # 4. List properties
    res = await obsidian_fs_property(PropertyInput(path="Props.md", operation="list"))
    data = json.loads(res)
    assert "test_key" in data
    
    # 5. Remove property
    res = await obsidian_fs_property(PropertyInput(path="Props.md", operation="remove", key="test_key"))
    assert '"status": "removed"' in res
    
    # 6. Verify removal
    res = await obsidian_fs_property(PropertyInput(path="Props.md", operation="get", key="test_key"))
    data = json.loads(res)
    # Depending on implementation, get might return null or empty dict for missing key? 
    # Current implementation returns json {key: None} if missing? 
    # Let's check fs_server: val = post.metadata.get(params.key) -> None if missing.
    # Current implementation returns json {key: None} if missing.
    assert data.get("test_key") is None

@pytest.mark.asyncio
async def test_properties_types(vault_dir):
    """Test properties with different types (list, bool, int)."""
    await obsidian_fs_create(CreateNoteInput(path="Types.md", content="# Types"))
    # 2. Set property
    res = await obsidian_fs_property(PropertyInput(path="Types.md", operation="set", key="tags", value=["a", "b"]))
    
    if "python-frontmatter not installed" in res:
        pytest.skip("python-frontmatter not installed; skipping property test")

    assert '"status": "set"' in res
    data = json.loads(await obsidian_fs_property(PropertyInput(path="Types.md", operation="get", key="tags")))
    assert data["tags"] == ["a", "b"]
    
    # Bool
    await obsidian_fs_property(PropertyInput(path="Types.md", operation="set", key="is_active", value=True))
    data = json.loads(await obsidian_fs_property(PropertyInput(path="Types.md", operation="get", key="is_active")))
    assert data["is_active"] is True
    
    # Number
    await obsidian_fs_property(PropertyInput(path="Types.md", operation="set", key="count", value=42))
    data = json.loads(await obsidian_fs_property(PropertyInput(path="Types.md", operation="get", key="count")))
    assert data["count"] == 42

