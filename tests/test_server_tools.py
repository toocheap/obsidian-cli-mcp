"""Unit tests for server.py — All 8 MCP tools for Obsidian CLI."""

from unittest.mock import patch, AsyncMock

import pytest

from server import (
    obsidian_daily_read,
    obsidian_daily_append,
    obsidian_tasks_list,
    obsidian_task_toggle,
    obsidian_search,
    obsidian_tags_list,
    obsidian_tag_info,
    obsidian_vault_info,
    VaultMixin,
    DailyAppendInput,
    TasksListInput,
    TaskToggleInput,
    SearchInput,
    TagsListInput,
    TagInfoInput,
)

from cli import ObsidianCLIError


# ---------------------------------------------------------------------------
# Daily Notes
# ---------------------------------------------------------------------------


class TestDailyRead:
    """Tests for obsidian_daily_read tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_basic(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "# 2025-02-11\n\nMy note"
        params = VaultMixin()
        result = await obsidian_daily_read(params)
        assert result == "# 2025-02-11\n\nMy note"
        mock_cli.assert_called_once_with("daily:read")

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_with_vault(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "content"
        params = VaultMixin(vault="MyVault")
        await obsidian_daily_read(params)
        mock_cli.assert_called_once_with("daily:read", vault="MyVault")

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_error(self, mock_cli: AsyncMock) -> None:
        mock_cli.side_effect = ObsidianCLIError("no vault", returncode=1, stderr="no vault")
        params = VaultMixin()
        result = await obsidian_daily_read(params)
        assert "Error" in result
        assert "no vault" in result


class TestDailyAppend:
    """Tests for obsidian_daily_append tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_basic(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = ""
        params = DailyAppendInput(content="Hello world")
        result = await obsidian_daily_append(params)
        assert result == "Content appended to daily note."
        mock_cli.assert_called_once_with("daily:append", "content=Hello world", "silent")

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_inline(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = ""
        params = DailyAppendInput(content="inline text", inline=True)
        await obsidian_daily_append(params)
        args = mock_cli.call_args[0]
        assert "inline" in args

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_error(self, mock_cli: AsyncMock) -> None:
        mock_cli.side_effect = ObsidianCLIError("write fail")
        params = DailyAppendInput(content="test")
        result = await obsidian_daily_append(params)
        assert "Error" in result


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TestTasksList:
    """Tests for obsidian_tasks_list tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_default(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "- [ ] Task 1\n- [x] Task 2"
        params = TasksListInput()
        result = await obsidian_tasks_list(params)
        assert "Task 1" in result
        args = mock_cli.call_args[0]
        assert "tasks" in args
        assert "verbose" in args

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_filters(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "tasks"
        params = TasksListInput(file="Recipe.md", todo=True, all_vault=True)
        await obsidian_tasks_list(params)
        args = mock_cli.call_args[0]
        assert "file=Recipe.md" in args
        assert "todo" in args
        assert "all" in args

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_daily_done_flags(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "tasks"
        params = TasksListInput(daily=True, done=True)
        await obsidian_tasks_list(params)
        args = mock_cli.call_args[0]
        assert "daily" in args
        assert "done" in args


class TestTaskToggle:
    """Tests for obsidian_task_toggle tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_toggle(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "toggled"
        params = TaskToggleInput(ref="Recipe.md:8")
        result = await obsidian_task_toggle(params)
        assert result == "toggled"
        mock_cli.assert_called_once_with("task", "ref=Recipe.md:8", "toggle")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for obsidian_search tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_basic(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "found 3 results"
        params = SearchInput(query="python")
        result = await obsidian_search(params)
        assert "found" in result
        args = mock_cli.call_args[0]
        assert "search" in args
        assert "query=python" in args
        assert "matches" in args

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_with_options(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "results"
        params = SearchInput(query="test", path="notes/", limit=5, matches=False)
        await obsidian_search(params)
        args = mock_cli.call_args[0]
        assert "path=notes/" in args
        assert "limit=5" in args
        assert "matches" not in args


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TestTagsList:
    """Tests for obsidian_tags_list tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_list(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "#python (5)\n#rust (3)"
        params = TagsListInput()
        result = await obsidian_tags_list(params)
        assert "#python" in result
        mock_cli.assert_called_once_with("tags", "all", "counts")


class TestTagInfo:
    """Tests for obsidian_tag_info tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_basic(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "tag details"
        params = TagInfoInput(name="python")
        result = await obsidian_tag_info(params)
        assert result == "tag details"
        mock_cli.assert_called_once_with("tag", "name=python", "verbose")

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_strip_hash(self, mock_cli: AsyncMock) -> None:
        """Leading # should be stripped from tag name."""
        mock_cli.return_value = "tag details"
        params = TagInfoInput(name="#python")
        await obsidian_tag_info(params)
        mock_cli.assert_called_once_with("tag", "name=python", "verbose")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


class TestVaultInfo:
    """Tests for obsidian_vault_info tool."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_basic(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "Vault: MyVault\nPath: /home/user/vault"
        params = VaultMixin()
        result = await obsidian_vault_info(params)
        assert "MyVault" in result
        mock_cli.assert_called_once_with("vault")

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_with_vault(self, mock_cli: AsyncMock) -> None:
        mock_cli.return_value = "info"
        params = VaultMixin(vault="Work")
        await obsidian_vault_info(params)
        mock_cli.assert_called_once_with("vault", vault="Work")


# ---------------------------------------------------------------------------
# Error handling (shared pattern)
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify all tools gracefully handle ObsidianCLIError."""

    @pytest.mark.asyncio
    @patch("server.run_obsidian_async", new_callable=AsyncMock)
    async def test_all_tools_return_error_string(self, mock_cli: AsyncMock) -> None:
        """Every tool should return an error string, not raise."""
        tools_and_params = [
            (obsidian_daily_read, VaultMixin()),
            (obsidian_daily_append, DailyAppendInput(content="x")),
            (obsidian_tasks_list, TasksListInput()),
            (obsidian_task_toggle, TaskToggleInput(ref="test.md:1")),
            (obsidian_search, SearchInput(query="test")),
            (obsidian_tags_list, TagsListInput()),
            (obsidian_tag_info, TagInfoInput(name="test")),
            (obsidian_vault_info, VaultMixin()),
        ]
        for tool_fn, params in tools_and_params:
            mock_cli.reset_mock()
            mock_cli.side_effect = ObsidianCLIError("CLI crashed", returncode=1, stderr="CLI crashed")
            result = await tool_fn(params)
            assert isinstance(result, str), f"{tool_fn.__name__} did not return str"
            assert "Error" in result, f"{tool_fn.__name__} missing 'Error' in response"
