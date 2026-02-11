"""Low-level wrapper for Obsidian CLI subprocess calls."""

import asyncio
import subprocess
import shutil
from typing import Optional


OBSIDIAN_CMD = "obsidian"
DEFAULT_TIMEOUT = 30


class ObsidianCLIError(Exception):
    """Raised when an Obsidian CLI command fails."""

    def __init__(self, message: str, returncode: int = -1, stderr: str = ""):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


def check_obsidian_available() -> bool:
    """Check if the obsidian CLI binary is available on PATH."""
    return shutil.which(OBSIDIAN_CMD) is not None


def run_obsidian(
    *args: str,
    vault: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Execute an Obsidian CLI command and return stdout.

    Args:
        *args: Command and arguments (e.g. "daily:read", "search", "query=test")
        vault: Optional vault name to target
        timeout: Command timeout in seconds

    Returns:
        str: Command stdout output

    Raises:
        ObsidianCLIError: If the command fails or times out
    """
    cmd = [OBSIDIAN_CMD]

    # Vault must come before the command
    if vault:
        cmd.append(f"vault={vault}")

    cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ObsidianCLIError(
            f"Command timed out after {timeout}s: {' '.join(cmd)}"
        )
    except FileNotFoundError:
        raise ObsidianCLIError(
            "Obsidian CLI not found. Make sure Obsidian 1.12+ is installed "
            "and CLI is enabled in Settings → General → Command line interface."
        )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ObsidianCLIError(
            f"Command failed (exit {result.returncode}): {stderr or result.stdout.strip()}",
            returncode=result.returncode,
            stderr=stderr,
        )

    return result.stdout.strip()


async def run_obsidian_async(
    *args: str,
    vault: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Async version of run_obsidian.

    Wraps the blocking subprocess call in asyncio.to_thread to avoid
    blocking the event loop in async MCP tool handlers.
    """
    return await asyncio.to_thread(run_obsidian, *args, vault=vault, timeout=timeout)

