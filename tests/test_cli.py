"""Unit tests for cli.py — Low-level Obsidian CLI wrapper."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio

from cli import (
    check_obsidian_available,
    run_obsidian,
    run_obsidian_async,
    ObsidianCLIError,
    OBSIDIAN_CMD,
)


# ---------------------------------------------------------------------------
# check_obsidian_available
# ---------------------------------------------------------------------------


class TestCheckObsidianAvailable:
    """Tests for check_obsidian_available()."""

    @patch("cli.shutil.which")
    def test_available(self, mock_which: MagicMock) -> None:
        mock_which.return_value = "/usr/local/bin/obsidian"
        assert check_obsidian_available() is True
        mock_which.assert_called_once_with(OBSIDIAN_CMD)

    @patch("cli.shutil.which")
    def test_not_available(self, mock_which: MagicMock) -> None:
        mock_which.return_value = None
        assert check_obsidian_available() is False


# ---------------------------------------------------------------------------
# run_obsidian
# ---------------------------------------------------------------------------


class TestRunObsidian:
    """Tests for run_obsidian() synchronous wrapper."""

    @patch("cli.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        """Successful CLI call returns stripped stdout."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  daily note content\n",
            stderr="",
        )
        result = run_obsidian("daily:read")
        assert result == "daily note content"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == [OBSIDIAN_CMD, "daily:read"]

    @patch("cli.subprocess.run")
    def test_with_vault(self, mock_run: MagicMock) -> None:
        """Vault argument is placed before the command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        run_obsidian("daily:read", vault="MyVault")
        cmd = mock_run.call_args[0][0]
        assert cmd == [OBSIDIAN_CMD, "vault=MyVault", "daily:read"]

    @patch("cli.subprocess.run")
    def test_multiple_args(self, mock_run: MagicMock) -> None:
        """Multiple arguments are passed through in order."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        run_obsidian("search", "query=test", "limit=10", vault="V")
        cmd = mock_run.call_args[0][0]
        assert cmd == [OBSIDIAN_CMD, "vault=V", "search", "query=test", "limit=10"]

    @patch("cli.subprocess.run")
    def test_failure_raises_error(self, mock_run: MagicMock) -> None:
        """Non-zero exit code raises ObsidianCLIError with details."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="vault not found",
        )
        with pytest.raises(ObsidianCLIError) as exc_info:
            run_obsidian("vault")
        assert exc_info.value.returncode == 1
        assert exc_info.value.stderr == "vault not found"
        assert "vault not found" in str(exc_info.value)

    @patch("cli.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        """TimeoutExpired is converted to ObsidianCLIError."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="obsidian", timeout=30)
        with pytest.raises(ObsidianCLIError, match="timed out"):
            run_obsidian("daily:read")

    @patch("cli.subprocess.run")
    def test_not_found(self, mock_run: MagicMock) -> None:
        """FileNotFoundError (CLI missing) becomes ObsidianCLIError."""
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(ObsidianCLIError, match="not found"):
            run_obsidian("daily:read")

    @patch("cli.subprocess.run")
    def test_custom_timeout(self, mock_run: MagicMock) -> None:
        """Custom timeout is passed to subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        run_obsidian("daily:read", timeout=60)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 60


# ---------------------------------------------------------------------------
# run_obsidian_async
# ---------------------------------------------------------------------------


class TestRunObsidianAsync:
    """Tests for run_obsidian_async() — async wrapper."""

    @pytest.mark.asyncio
    @patch("cli.subprocess.run")
    async def test_async_returns_same_result(self, mock_run: MagicMock) -> None:
        """Async wrapper returns the same result as sync version."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="async result\n",
            stderr="",
        )
        result = await run_obsidian_async("daily:read", vault="V")
        assert result == "async result"
        cmd = mock_run.call_args[0][0]
        assert cmd == [OBSIDIAN_CMD, "vault=V", "daily:read"]

    @pytest.mark.asyncio
    @patch("cli.subprocess.run")
    async def test_async_propagates_error(self, mock_run: MagicMock) -> None:
        """Async wrapper propagates ObsidianCLIError from sync version."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error msg"
        )
        with pytest.raises(ObsidianCLIError):
            await run_obsidian_async("vault")
