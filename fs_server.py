#!/usr/bin/env python3
"""
Obsidian Filesystem MCP Server

Alternative MCP server that directly accesses the vault filesystem
instead of using the Obsidian CLI binary. Useful when:
- Obsidian CLI (1.12+) is not available
- You want to operate on vault files without Obsidian running
- You need additional features like backlink analysis and tag extraction

Required environment variable:
    OBSIDIAN_VAULT_PATH - Absolute path to your Obsidian vault directory

Can be used alongside or instead of the CLI-based server.py.
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from enum import Enum
from functools import lru_cache

try:
    import frontmatter
except ImportError:
    frontmatter = None

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "")
DEFAULT_DAILY_NOTE_FORMAT = "%Y-%m-%d"
DEFAULT_DAILY_NOTE_FOLDER = ""
MAX_SEARCH_RESULTS = 100
DEFAULT_SEARCH_LIMIT = 20
WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
TAG_PATTERN = re.compile(r"(?<=\s)#([a-zA-Z0-9_\-/]+)", re.MULTILINE)
FRONTMATTER_TAG_PATTERN = re.compile(r"^tags:\s*\[?(.*?)\]?\s*$", re.MULTILINE)
TASK_PATTERN = re.compile(r"^(\s*)-\s\[(.)\]\s+(.*)$")

# ---------------------------------------------------------------------------
# Logging (stderr only for stdio transport)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("obsidian_fs_mcp")

# ---------------------------------------------------------------------------
# Server Initialization
# ---------------------------------------------------------------------------

mcp = FastMCP("obsidian_fs_mcp")

# ---------------------------------------------------------------------------
# Response format
# ---------------------------------------------------------------------------


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _vault_path() -> Path:
    """Return the validated vault path. Cached after first call."""
    if not VAULT_PATH:
        raise ValueError(
            "OBSIDIAN_VAULT_PATH environment variable is not set. "
            "Please set it to your Obsidian vault directory."
        )
    p = Path(VAULT_PATH).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"Vault path does not exist or is not a directory: {p}")
    return p


def _safe_resolve(vault: Path, relative: str) -> Path:
    """Resolve a relative path within the vault, preventing directory traversal.

    Note: symlinks within the vault that point outside are resolved and
    will be rejected by is_relative_to(). This is intentional.
    """
    resolved = (vault / relative).resolve()
    if not resolved.is_relative_to(vault):
        raise ValueError(f"Path traversal detected: {relative}")
    return resolved


def _is_hidden(path: Path) -> bool:
    """Check if any component of the path starts with '.' (hidden files/folders)."""
    return any(part.startswith(".") for part in path.parts)


def _list_notes(vault: Path, folder: Optional[str] = None) -> List[Path]:
    """List all markdown files in the vault or a specific folder."""
    base = _safe_resolve(vault, folder) if folder else vault
    notes = []
    for p in base.rglob("*.md"):
        if not _is_hidden(p.relative_to(vault)):
            notes.append(p)
    return sorted(notes)


def _strip_code_blocks(content: str) -> str:
    """Remove fenced code blocks and inline code from content."""
    content = re.sub(r'```[\s\S]*?```', '', content)
    content = re.sub(r'`[^`]+`', '', content)
    return content


def _extract_tags(content: str) -> List[str]:
    """Extract tags from note content (inline #tags and frontmatter tags).

    Strips code blocks first to avoid false positives. Uses lookbehind
    for whitespace to exclude Markdown headings (# Heading).
    """
    tags = set()
    stripped = _strip_code_blocks(content)
    for match in TAG_PATTERN.finditer(stripped):
        tags.add(match.group(1))
    
    # Use python-frontmatter if available for robust parsing
    if frontmatter:
        try:
            fm = frontmatter.loads(content)
            if fm.get("tags"):
                fm_tags = fm["tags"]
                if isinstance(fm_tags, list):
                    tags.update(str(t) for t in fm_tags)
                elif isinstance(fm_tags, str):
                    tags.update(t.strip() for t in fm_tags.split(","))
        except Exception:
            pass
    
    # Fallback/Supplemental regex for frontmatter (if python-frontmatter failed or not installed)
    for match in FRONTMATTER_TAG_PATTERN.finditer(content):
        raw = match.group(1)
        for tag in re.split(r"[,\s]+", raw):
            tag = tag.strip().strip("#").strip("'\"" )
            if tag:
                tags.add(tag)
    return sorted(tags)


def _extract_wikilinks(content: str) -> List[str]:
    """Extract [[wikilinks]] from note content."""
    return sorted(set(WIKILINK_PATTERN.findall(content)))


def _note_metadata(vault: Path, note_path: Path, include_frontmatter: bool = False) -> Dict[str, Any]:
    """Build metadata dict for a note."""
    rel = note_path.relative_to(vault)
    stat = note_path.stat()
    meta: Dict[str, Any] = {
        "path": str(rel),
        "name": note_path.stem,
        "folder": str(rel.parent) if str(rel.parent) != "." else "",
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        # Note: st_ctime is creation time on macOS, but metadata change time on Linux
        "created": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
    }
    if include_frontmatter and frontmatter:
        try:
            post = frontmatter.load(note_path)
            meta["frontmatter"] = post.metadata
        except Exception:
            meta["frontmatter"] = {}
    return meta


# ---------------------------------------------------------------------------
# Input Models
# ---------------------------------------------------------------------------


class SearchNotesInput(BaseModel):
    """Input for searching notes by filename or content."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(..., description="Search query string", min_length=1, max_length=500)
    search_type: Literal["filename", "content", "both"] = Field(
        default="both",
        description="Search type: 'filename', 'content', or 'both'",
    )
    folder: Optional[str] = Field(default=None, description="Limit search to a specific folder")
    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, description="Max results to return", ge=1, le=MAX_SEARCH_RESULTS)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class ReadNoteInput(BaseModel):
    """Input for reading a note."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Relative path to the note (e.g., 'folder/note.md')", min_length=1)


class CreateNoteInput(BaseModel):
    """Input for creating a new note."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Relative path for the new note (e.g., 'folder/note.md')", min_length=1)
    content: str = Field(default="", description="Initial content for the note")
    overwrite: bool = Field(default=False, description="Overwrite if the note already exists")


class EditNoteInput(BaseModel):
    """Input for editing an existing note."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Relative path to the note", min_length=1)
    operation: str = Field(
        ...,
        description="Edit operation: 'append', 'prepend', or 'replace'",
        pattern=r"^(append|prepend|replace)$",
    )
    content: str = Field(..., description="Content to add or replace with")
    find: Optional[str] = Field(
        default=None,
        description="For 'replace' operation: the text to find and replace",
    )


class DeleteNoteInput(BaseModel):
    """Input for deleting a note."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Relative path to the note to delete", min_length=1)
    confirm: bool = Field(default=False, description="Must be true to confirm deletion")


class ListFolderInput(BaseModel):
    """Input for listing folder contents."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    folder: Optional[str] = Field(default=None, description="Folder path relative to vault root")
    depth: int = Field(default=2, description="Max depth to list", ge=1, le=5)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetTagsInput(BaseModel):
    """Input for listing all tags in the vault."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    folder: Optional[str] = Field(default=None, description="Limit to a specific folder")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class GetBacklinksInput(BaseModel):
    """Input for finding backlinks to a note."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    note_name: str = Field(
        ...,
        description="Note name (without .md extension) to find backlinks for",
        min_length=1,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format")


class CreateDailyNoteInput(BaseModel):
    """Input for creating a daily note."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    date: Optional[str] = Field(
        default=None,
        description="Date in YYYY-MM-DD format (defaults to today)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    folder: Optional[str] = Field(default=None, description="Folder for daily notes")
    template: Optional[str] = Field(
        default=None,
        description="Path to a template note to use for content",
    )


class FsTasksListInput(BaseModel):
    """Input for listing tasks in the vault."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    folder: Optional[str] = Field(default=None, description="Limit to a specific folder")
    todo: bool = Field(default=False, description="Show only incomplete tasks")
    done: bool = Field(default=False, description="Show only completed tasks")


class FsTaskToggleInput(BaseModel):
    """Input for toggling a task status."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(..., description="Path to the note containing the task")
    line: int = Field(..., description="Line number of the task (1-indexed)", ge=1)


class MoveNoteInput(BaseModel):
    """Input for moving or renaming a note/folder."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source: str = Field(..., description="Current path of the note or folder", min_length=1)
    destination: str = Field(..., description="New path for the note or folder", min_length=1)
    overwrite: bool = Field(default=False, description="Overwrite if destination exists")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(name="obsidian_fs_search")
async def obsidian_fs_search(params: SearchNotesInput) -> str:
    """Search notes in the Obsidian vault by filename, content, or both.

    Args:
        params (SearchNotesInput): Search parameters including query, type, folder, limit.

    Returns:
        str: Search results in the requested format.
    """
    vault = _vault_path()
    notes = _list_notes(vault, params.folder)
    query_lower = params.query.lower()
    results: List[Dict[str, Any]] = []

    for note_path in notes:
        if len(results) >= params.limit:
            break
        matched = False
        match_context = ""
        if params.search_type in ("filename", "both"):
            if query_lower in note_path.stem.lower():
                matched = True
        if params.search_type in ("content", "both") and not matched:
            try:
                content = note_path.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    matched = True
                    idx = content.lower().find(query_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(params.query) + 50)
                    match_context = content[start:end].replace("\n", " ").strip()
            except (UnicodeDecodeError, OSError):
                continue
        if matched:
            meta = _note_metadata(vault, note_path, include_frontmatter=True)
            meta["match_context"] = match_context
            results.append(meta)

    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"total": len(results), "query": params.query, "results": results}, indent=2)
    lines = [f"# Search Results for '{params.query}' ({len(results)} found)\n"]
    for r in results:
        line = f"- **{r['name']}** (`{r['path']}`)"
        if r.get("match_context"):
            line += f"\n  > ...{r['match_context']}..."
        lines.append(line)
    return "\n".join(lines) if results else f"No results found for '{params.query}'."


@mcp.tool(name="obsidian_fs_read")
async def obsidian_fs_read(params: ReadNoteInput) -> str:
    """Read the full content of a note including metadata, tags, and wikilinks.

    Args:
        params (ReadNoteInput): Path to the note.

    Returns:
        str: JSON with note metadata, content, tags, and wikilinks.
    """
    vault = _vault_path()
    note_path = _safe_resolve(vault, params.path)
    if not note_path.suffix:
        note_path = note_path.with_suffix(".md")
    if not note_path.is_file():
        return f"Error: Note not found at '{params.path}'."
    try:
        content = note_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return f"Error: Could not read note: {e}"
    meta = _note_metadata(vault, note_path)
    meta["content"] = content
    
    if frontmatter:
        try:
            post = frontmatter.loads(content)
            meta["frontmatter"] = post.metadata
        except Exception:
            meta["frontmatter"] = {}
            
    meta["tags"] = _extract_tags(content)
    meta["wikilinks"] = _extract_wikilinks(content)
    meta["word_count"] = len(content.split())
    meta["char_count"] = len(content)
    return json.dumps(meta, indent=2, ensure_ascii=False)


@mcp.tool(name="obsidian_fs_create")
async def obsidian_fs_create(params: CreateNoteInput) -> str:
    """Create a new note in the vault.

    Args:
        params (CreateNoteInput): Path, content, and overwrite flag.

    Returns:
        str: JSON with creation status.
    """
    vault = _vault_path()
    note_path = _safe_resolve(vault, params.path)
    if not note_path.suffix:
        note_path = note_path.with_suffix(".md")
    if note_path.exists() and not params.overwrite:
        return f"Error: Note already exists at '{params.path}'. Set overwrite=true to replace."
    try:
        note_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return f"Error: Could not create directory: {e}"
    try:
        note_path.write_text(params.content, encoding="utf-8")
    except OSError as e:
        return f"Error: Could not create note: {e}"
    rel = note_path.relative_to(vault)
    return json.dumps({"status": "created", "path": str(rel), "size_bytes": len(params.content.encode("utf-8"))}, indent=2)


@mcp.tool(name="obsidian_fs_edit")
async def obsidian_fs_edit(params: EditNoteInput) -> str:
    """Edit an existing note (append, prepend, or replace).

    Args:
        params (EditNoteInput): Path, operation, content, and optional find text.

    Returns:
        str: JSON with edit status.
    """
    vault = _vault_path()
    note_path = _safe_resolve(vault, params.path)
    if not note_path.suffix:
        note_path = note_path.with_suffix(".md")
    if not note_path.is_file():
        return f"Error: Note not found at '{params.path}'."
    try:
        original = note_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return f"Error: Could not read note: {e}"
    if params.operation == "append":
        new_content = original + "\n" + params.content
    elif params.operation == "prepend":
        new_content = params.content + "\n" + original
    elif params.operation == "replace":
        if params.find is None:
            new_content = params.content
        else:
            find_text = str(params.find)
            if find_text not in original:
                return f"Error: Text to replace not found in '{params.path}'."
            new_content = original.replace(find_text, params.content, 1)
    else:
        return f"Error: Unknown operation '{params.operation}'."
    try:
        note_path.write_text(new_content, encoding="utf-8")
    except OSError as e:
        return f"Error: Could not write note: {e}"
    return json.dumps({"status": "edited", "path": str(note_path.relative_to(vault)), "operation": params.operation, "original_size": len(original), "new_size": len(new_content)}, indent=2)


@mcp.tool(name="obsidian_fs_delete")
async def obsidian_fs_delete(params: DeleteNoteInput) -> str:
    """Delete a note from the vault. Requires confirm=true.

    Args:
        params (DeleteNoteInput): Path and confirmation flag.

    Returns:
        str: JSON with deletion status.
    """
    if not params.confirm:
        return "Error: Deletion not confirmed. Set confirm=true to proceed."
    vault = _vault_path()
    note_path = _safe_resolve(vault, params.path)
    if not note_path.suffix:
        note_path = note_path.with_suffix(".md")
    if not note_path.is_file():
        return f"Error: Note not found at '{params.path}'."
    rel = str(note_path.relative_to(vault))
    try:
        note_path.unlink()
    except OSError as e:
        return f"Error: Could not delete note: {e}"
    return json.dumps({"status": "deleted", "path": rel}, indent=2)


@mcp.tool(name="obsidian_fs_list_folder")
async def obsidian_fs_list_folder(params: ListFolderInput) -> str:
    """List the folder structure and notes in the vault.

    Args:
        params (ListFolderInput): Folder path, depth, and format.

    Returns:
        str: Folder listing in the requested format.
    """
    vault = _vault_path()
    base = _safe_resolve(vault, str(params.folder)) if params.folder else vault
    if not base.is_dir():
        return f"Error: Folder not found: '{params.folder}'"

    def _walk(directory: Path, current_depth: int) -> List[Dict[str, Any]]:
        items = []
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except OSError:
            return items
        for entry in entries:
            rel = entry.relative_to(vault)
            if _is_hidden(rel):
                continue
            if entry.is_dir():
                children = _walk(entry, current_depth + 1) if current_depth < params.depth else []
                items.append({"type": "folder", "name": entry.name, "path": str(rel), "children": children})
            elif entry.suffix == ".md":
                items.append({"type": "note", "name": entry.stem, "path": str(rel)})
        return items

    tree = _walk(base, 1)
    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"root": params.folder or "/", "items": tree}, indent=2, ensure_ascii=False)

    def _render_tree(items: List[Dict], indent: int = 0) -> List[str]:
        lines = []
        prefix = "  " * indent
        for item in items:
            if item["type"] == "folder":
                lines.append(f"{prefix}📁 **{item['name']}/**")
                lines.extend(_render_tree(item.get("children", []), indent + 1))
            else:
                lines.append(f"{prefix}📄 {item['name']} (`{item['path']}`)")
        return lines

    header = f"# Vault Structure: {params.folder or '/'}\n"
    return header + "\n".join(_render_tree(tree))


@mcp.tool(name="obsidian_fs_get_tags")
async def obsidian_fs_get_tags(params: GetTagsInput) -> str:
    """Get all tags used across notes in the vault with counts.

    Args:
        params (GetTagsInput): Optional folder filter and format.

    Returns:
        str: Tag listing with counts.
    """
    vault = _vault_path()
    notes = _list_notes(vault, params.folder)
    tag_counts: Dict[str, int] = {}
    for note_path in notes:
        try:
            content = note_path.read_text(encoding="utf-8")
            for tag in _extract_tags(content):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        except (UnicodeDecodeError, OSError):
            continue
    sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"total_tags": len(sorted_tags), "tags": [{"tag": t, "count": c} for t, c in sorted_tags]}, indent=2)
    lines = [f"# Tags ({len(sorted_tags)} found)\n"]
    for tag, count in sorted_tags:
        lines.append(f"- #{tag} ({count} notes)")
    return "\n".join(lines) if sorted_tags else "No tags found in the vault."


@mcp.tool(name="obsidian_fs_get_backlinks")
async def obsidian_fs_get_backlinks(params: GetBacklinksInput) -> str:
    """Find all notes that link to a specific note via [[wikilinks]].

    Args:
        params (GetBacklinksInput): Target note name and format.

    Returns:
        str: List of notes containing backlinks to the target.
    """
    vault = _vault_path()
    notes = _list_notes(vault)
    target = params.note_name.lower()
    backlinks: List[Dict[str, Any]] = []
    for note_path in notes:
        try:
            content = note_path.read_text(encoding="utf-8")
            links = _extract_wikilinks(content)
            if any(link.lower() == target for link in links):
                backlinks.append(_note_metadata(vault, note_path))
        except (UnicodeDecodeError, OSError):
            continue
    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"target": params.note_name, "total": len(backlinks), "backlinks": backlinks}, indent=2)
    lines = [f"# Backlinks to '{params.note_name}' ({len(backlinks)} found)\n"]
    for bl in backlinks:
        lines.append(f"- **{bl['name']}** (`{bl['path']}`)")
    return "\n".join(lines) if backlinks else f"No backlinks found for '{params.note_name}'."


@mcp.tool(name="obsidian_fs_daily_note")
async def obsidian_fs_daily_note(params: CreateDailyNoteInput) -> str:
    """Create a daily note for the specified date (defaults to today).

    Args:
        params (CreateDailyNoteInput): Date, folder, and template options.

    Returns:
        str: JSON with creation status or existing note content.
    """
    vault = _vault_path()
    date_str = params.date
    if date_str is not None:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return "Error: Invalid date format. Use YYYY-MM-DD."
    else:
        dt = datetime.now()
    filename = dt.strftime(DEFAULT_DAILY_NOTE_FORMAT) + ".md"
    folder = params.folder or DEFAULT_DAILY_NOTE_FOLDER
    rel_path = f"{folder}/{filename}" if folder else filename
    note_path = _safe_resolve(vault, rel_path)
    if note_path.exists():
        try:
            content = note_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            return f"Error: Could not read existing daily note: {e}"
        return json.dumps({"status": "already_exists", "path": rel_path, "content": content}, indent=2, ensure_ascii=False)
    content = f"# {dt.strftime('%Y-%m-%d %A')}\n\n"
    if params.template is not None:
        template_path = _safe_resolve(vault, str(params.template))
        if template_path.is_file():
            try:
                tmpl = template_path.read_text(encoding="utf-8")
                content = tmpl.replace("{{date}}", dt.strftime("%Y-%m-%d"))
                content = content.replace("{{title}}", dt.strftime("%Y-%m-%d %A"))
            except (UnicodeDecodeError, OSError):
                pass
    try:
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"Error: Could not create daily note: {e}"
    return json.dumps({"status": "created", "path": rel_path, "date": dt.strftime("%Y-%m-%d")}, indent=2)


@mcp.tool(name="obsidian_fs_tasks_list")
async def obsidian_fs_tasks_list(params: FsTasksListInput) -> str:
    """List tasks from the vault.

    Args:
        params (FsTasksListInput): Filters for folder and status.

    Returns:
        str: List of tasks.
    """
    vault = _vault_path()
    notes = _list_notes(vault, params.folder)
    tasks = []

    for note_path in notes:
        try:
            content = note_path.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), start=1):
                match = TASK_PATTERN.match(line)
                if match:
                    status = match.group(2)
                    text = match.group(3)
                    is_done = status != " "
                    
                    if params.todo and is_done:
                        continue
                    if params.done and not is_done:
                        continue

                    rel_path = str(note_path.relative_to(vault))
                    tasks.append(f"- [{status}] {text} ({rel_path}:{i})")
        except (UnicodeDecodeError, OSError):
            continue
            
    if not tasks:
        return "No tasks found."
    return f"# Tasks ({len(tasks)} tasks found)\n" + "\n".join(tasks)


@mcp.tool(name="obsidian_fs_task_toggle")
async def obsidian_fs_task_toggle(params: FsTaskToggleInput) -> str:
    """Toggle the status of a task at a specific line.

    Args:
        params (FsTaskToggleInput): File path and line number.

    Returns:
        str: Status message.
    """
    vault = _vault_path()
    note_path = _safe_resolve(vault, params.path)
    
    if not note_path.suffix:
        note_path = note_path.with_suffix(".md")
    
    if not note_path.is_file():
        return f"Error: Note not found at '{params.path}'."

    try:
        lines = note_path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError) as e:
        return f"Error: Could not read note: {e}"

    if params.line > len(lines):
        return f"Error: Line {params.line} exceeds file length ({len(lines)} lines)."

    target_line_idx = params.line - 1
    line_content = lines[target_line_idx]
    match = TASK_PATTERN.match(line_content)
    
    if not match:
        return f"Error: Line {params.line} in {params.path} is not a task."

    indent = match.group(1)
    status = match.group(2)
    text = match.group(3)
    
    new_status = " " if status != " " else "x"
    lines[target_line_idx] = f"{indent}- [{new_status}] {text}"
    
    try:
        note_path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as e:
        return f"Error: Could not write note: {e}"
        
    rel_path = str(note_path.relative_to(vault))
    return f"Toggled task at {rel_path}:{params.line} to [{new_status}]"


@mcp.tool(name="obsidian_fs_move")
async def obsidian_fs_move(params: MoveNoteInput) -> str:
    """Move or rename a note or folder.

    Args:
        params (MoveNoteInput): Source, destination, and overwrite flag.

    Returns:
        str: JSON with move status.
    """
    vault = _vault_path()
    src_path = _safe_resolve(vault, params.source)
    dest_path = _safe_resolve(vault, params.destination)
    
    # Handle suffixes for files implies .md if missing, but for generic move we might want to be strict?
    # Spec implied "MoveNote" but also "folder".
    # If source exists, we know what it is.
    
    if not src_path.exists():
        # Try appending .md if it's a file move attempt
        if not src_path.suffix and src_path.with_suffix(".md").exists():
             src_path = src_path.with_suffix(".md")
        else:
            return f"Error: Source not found: '{params.source}'"
            
    # If source is a file and dest has no suffix, assume .md?
    # Or just let user specify. Let's assume .md if source is .md and dest has no suffix.
    if src_path.is_file() and not dest_path.suffix and dest_path.name != dest_path.stem: # .name != .stem means has suffix
         pass # has suffix
    elif src_path.is_file() and not dest_path.suffix:
         dest_path = dest_path.with_suffix(".md")

    if dest_path.exists() and not params.overwrite:
        return f"Error: Destination already exists: '{params.destination}'. Set overwrite=true to force."

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        # shutil.move is safer for cross-filesystem but os.replace is atomic on POSIX
        # We use renames within valid vault, so path.rename is fine (calls os.rename)
        # But os.rename fails if dest exists on Windows, os.replace works.
        # pathlib.Path.replace calls os.replace.
        src_path.replace(dest_path)
    except OSError as e:
        return f"Error: Could not move: {e}"

    return json.dumps({
        "status": "moved", 
        "from": str(src_path.relative_to(vault)), 
        "to": str(dest_path.relative_to(vault))
    }, indent=2)


# ---------------------------------------------------------------------------
# Universal Aliases (Drop-in replacements for server.py tools)
# ---------------------------------------------------------------------------

@mcp.tool(name="obsidian_search")
async def alias_obsidian_search(params: SearchNotesInput) -> str:
    """Alias for obsidian_fs_search."""
    return await obsidian_fs_search(params)

@mcp.tool(name="obsidian_read")
async def alias_obsidian_read(params: ReadNoteInput) -> str:
    """Alias for obsidian_fs_read."""
    return await obsidian_fs_read(params)

@mcp.tool(name="obsidian_create")
async def alias_obsidian_create(params: CreateNoteInput) -> str:
    """Alias for obsidian_fs_create."""
    return await obsidian_fs_create(params)

@mcp.tool(name="obsidian_edit")
async def alias_obsidian_edit(params: EditNoteInput) -> str:
    """Alias for obsidian_fs_edit."""
    return await obsidian_fs_edit(params)

@mcp.tool(name="obsidian_delete")
async def alias_obsidian_delete(params: DeleteNoteInput) -> str:
    """Alias for obsidian_fs_delete."""
    return await obsidian_fs_delete(params)

@mcp.tool(name="obsidian_list_folder")
async def alias_obsidian_list_folder(params: ListFolderInput) -> str:
    """Alias for obsidian_fs_list_folder."""
    return await obsidian_fs_list_folder(params)

@mcp.tool(name="obsidian_tags_list")
async def alias_obsidian_tags_list(params: GetTagsInput) -> str:
    """Alias for obsidian_fs_get_tags. Lists all tags."""
    return await obsidian_fs_get_tags(params)

@mcp.tool(name="obsidian_backlinks")
async def alias_obsidian_backlinks(params: GetBacklinksInput) -> str:
    """Alias for obsidian_fs_get_backlinks."""
    return await obsidian_fs_get_backlinks(params)

@mcp.tool(name="obsidian_tasks_list")
async def alias_obsidian_tasks_list(params: FsTasksListInput) -> str:
    """Alias for obsidian_fs_tasks_list."""
    return await obsidian_fs_tasks_list(params)

@mcp.tool(name="obsidian_task_toggle")
async def alias_obsidian_task_toggle(params: FsTaskToggleInput) -> str:
    """Alias for obsidian_fs_task_toggle."""
    return await obsidian_fs_task_toggle(params)

class DailyAppendInput(BaseModel):
    """Input for appending to daily note."""
    content: str = Field(..., description="Content to append")

@mcp.tool(name="obsidian_daily_read")
async def alias_obsidian_daily_read() -> str:
    """Read today's daily note (creates it if missing)."""
    return await obsidian_fs_daily_note(CreateDailyNoteInput())

@mcp.tool(name="obsidian_daily_append")
async def alias_obsidian_daily_append(params: DailyAppendInput) -> str:
    """Append content to today's daily note."""
    # 1. Ensure exists
    res_json = await obsidian_fs_daily_note(CreateDailyNoteInput())
    res = json.loads(res_json)
    path = res["path"]
    
    # 2. Append
    return await obsidian_fs_edit(EditNoteInput(
        path=path,
        operation="append",
        content=params.content
    ))

@mcp.tool(name="obsidian_vault_info")
async def alias_obsidian_vault_info() -> str:
    """Get vault statistics."""
    vault = _vault_path()
    notes = _list_notes(vault)
    return json.dumps({
        "name": vault.name,
        "path": str(vault),
        "total_notes": len(notes),
        "total_size_bytes": sum(n.stat().st_size for n in notes)
    }, indent=2)

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    """Entry point for the FS MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
