"""Obsidian CLI MCP Server - Control Obsidian from Claude."""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

from cli import run_obsidian_async, ObsidianCLIError

mcp = FastMCP("obsidian_mcp")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _error_response(e: Exception) -> str:
    """Format an error into an actionable message."""
    if isinstance(e, ObsidianCLIError):
        return f"Error: {e}"
    return f"Unexpected error: {type(e).__name__}: {e}"


def _vault_args(vault: Optional[str]) -> dict:
    """Build vault kwarg for run_obsidian."""
    return {"vault": vault} if vault else {}


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class VaultMixin(BaseModel):
    """Common vault parameter."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    vault: Optional[str] = Field(
        default=None,
        description="Vault name. Defaults to the active vault if omitted.",
    )


class DailyAppendInput(VaultMixin):
    """Input for appending content to the daily note."""
    content: str = Field(
        ..., description="Text to append to the daily note.", min_length=1
    )
    inline: bool = Field(
        default=False, description="If true, append without a leading newline."
    )


class TasksListInput(VaultMixin):
    """Input for listing tasks."""
    file: Optional[str] = Field(default=None, description="Filter by file name.")
    todo: bool = Field(default=False, description="Show only incomplete tasks.")
    done: bool = Field(default=False, description="Show only completed tasks.")
    daily: bool = Field(default=False, description="Show tasks from the daily note.")
    all_vault: bool = Field(default=False, description="List all tasks in the vault.")


class TaskToggleInput(VaultMixin):
    """Input for toggling a task."""
    ref: str = Field(
        ...,
        description="Task reference in 'path:line' format (e.g. 'Recipe.md:8').",
        min_length=1,
    )


class SearchInput(VaultMixin):
    """Input for searching the vault."""
    query: str = Field(..., description="Search query text.", min_length=1)
    path: Optional[str] = Field(default=None, description="Limit search to a folder.")
    limit: Optional[int] = Field(
        default=None, description="Max number of results.", ge=1, le=200
    )
    matches: bool = Field(default=True, description="Show match context.")


class TagsListInput(VaultMixin):
    """Input for listing tags."""
    pass


class TagInfoInput(VaultMixin):
    """Input for getting info about a specific tag."""
    name: str = Field(
        ..., description="Tag name (with or without #).", min_length=1
    )


# ---------------------------------------------------------------------------
# Tools: Daily Notes
# ---------------------------------------------------------------------------

@mcp.tool(name="obsidian_daily_read")
async def obsidian_daily_read(params: VaultMixin) -> str:
    """Read the contents of today's daily note.

    Returns the full text of the daily note. Creates it first if it
    does not exist yet (using the configured daily note template).
    """
    try:
        return await run_obsidian_async("daily:read", **_vault_args(params.vault))
    except ObsidianCLIError as e:
        return _error_response(e)


@mcp.tool(name="obsidian_daily_append")
async def obsidian_daily_append(params: DailyAppendInput) -> str:
    """Append text to today's daily note.

    Use this to add tasks, notes, or any content to the end of
    the daily note. Supports markdown and \\n for newlines.
    """
    try:
        args = ["daily:append", f'content={params.content}', "silent"]
        if params.inline:
            args.append("inline")
        return await run_obsidian_async(*args, **_vault_args(params.vault)) or "Content appended to daily note."
    except ObsidianCLIError as e:
        return _error_response(e)


# ---------------------------------------------------------------------------
# Tools: Tasks
# ---------------------------------------------------------------------------

@mcp.tool(name="obsidian_tasks_list")
async def obsidian_tasks_list(params: TasksListInput) -> str:
    """List tasks from the vault, a specific file, or the daily note.

    Supports filtering by completion status (todo/done) and by file.
    """
    try:
        args = ["tasks"]
        if params.file:
            args.append(f"file={params.file}")
        if params.all_vault:
            args.append("all")
        if params.daily:
            args.append("daily")
        if params.todo:
            args.append("todo")
        if params.done:
            args.append("done")
        args.append("verbose")
        return await run_obsidian_async(*args, **_vault_args(params.vault))
    except ObsidianCLIError as e:
        return _error_response(e)


@mcp.tool(name="obsidian_task_toggle")
async def obsidian_task_toggle(params: TaskToggleInput) -> str:
    """Toggle a task between complete and incomplete."""
    try:
        return await run_obsidian_async("task", f"ref={params.ref}", "toggle", **_vault_args(params.vault))
    except ObsidianCLIError as e:
        return _error_response(e)


# ---------------------------------------------------------------------------
# Tools: Search
# ---------------------------------------------------------------------------

@mcp.tool(name="obsidian_search")
async def obsidian_search(params: SearchInput) -> str:
    """Search the vault for text.

    Returns matching files and optionally match context.
    """
    try:
        args = ["search", f"query={params.query}"]
        if params.path:
            args.append(f"path={params.path}")
        if params.limit:
            args.append(f"limit={params.limit}")
        if params.matches:
            args.append("matches")
        return await run_obsidian_async(*args, **_vault_args(params.vault))
    except ObsidianCLIError as e:
        return _error_response(e)


# ---------------------------------------------------------------------------
# Tools: Tags
# ---------------------------------------------------------------------------

@mcp.tool(name="obsidian_tags_list")
async def obsidian_tags_list(params: TagsListInput) -> str:
    """List all tags in the vault with occurrence counts."""
    try:
        return await run_obsidian_async("tags", "all", "counts", **_vault_args(params.vault))
    except ObsidianCLIError as e:
        return _error_response(e)


@mcp.tool(name="obsidian_tag_info")
async def obsidian_tag_info(params: TagInfoInput) -> str:
    """Get details about a specific tag, including which files use it."""
    try:
        tag = params.name.lstrip("#")
        return await run_obsidian_async("tag", f"name={tag}", "verbose", **_vault_args(params.vault))
    except ObsidianCLIError as e:
        return _error_response(e)


# ---------------------------------------------------------------------------
# Tools: Utility
# ---------------------------------------------------------------------------

@mcp.tool(name="obsidian_vault_info")
async def obsidian_vault_info(params: VaultMixin) -> str:
    """Show vault information (name, path, file/folder counts, size)."""
    try:
        return await run_obsidian_async("vault", **_vault_args(params.vault))
    except ObsidianCLIError as e:
        return _error_response(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
