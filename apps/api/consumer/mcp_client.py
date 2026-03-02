"""MCP stdio client for the Playwright MCP server.

Spawns the MCP server as a subprocess and communicates with it via
JSON-RPC 2.0 over stdin/stdout (the MCP stdio transport).
"""

import asyncio
import json
import logging
import shlex
import sys
from types import TracebackType
from typing import Any, cast

logger = logging.getLogger(__name__)

_JSONRPC_VERSION = "2.0"
_MCP_PROTOCOL_VERSION = "2024-11-05"


class MCPClient:
    """Async context manager that manages a Playwright MCP subprocess."""

    def __init__(self, command: str) -> None:
        self._command = command
        self._proc: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._tools: list[dict[str, Any]] = []
        self._stderr_task: asyncio.Task[None] | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def __aenter__(self) -> "MCPClient":
        # On Windows, executables like `npx` are .cmd shell scripts that
        # create_subprocess_exec cannot resolve without the shell.
        if sys.platform == "win32":
            self._proc = await asyncio.create_subprocess_shell(
                self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            args = shlex.split(self._command)
            self._proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        logger.info("MCP server started (pid=%s)", self._proc.pid)

        # Drain stderr continuously so it appears in logs immediately
        self._stderr_task = asyncio.create_task(self._drain_stderr())

        await self._initialize()
        self._tools = await self._list_tools()
        logger.info("MCP server ready — %d tools available", len(self._tools))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                if sys.platform == "win32":
                    # On Windows, cmd.exe is the direct child but Chrome is a
                    # grandchild. taskkill /T propagates termination to the
                    # whole process tree so Chrome can flush and finalize files.
                    proc = await asyncio.create_subprocess_exec(
                        "taskkill", "/T", "/PID", str(self._proc.pid),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.wait_for(proc.wait(), timeout=2)
                else:
                    self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=10)
            except Exception:
                self._proc.kill()

        if self._stderr_task:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except (asyncio.CancelledError, Exception):
                pass

        logger.info("MCP server stopped")

    async def _drain_stderr(self) -> None:
        """Read stderr line-by-line and emit each line as a log message."""
        assert self._proc and self._proc.stderr
        try:
            async for line in self._proc.stderr:
                text = line.decode(errors="replace").rstrip()
                if text:
                    logger.warning("MCP stderr: %s", text)
        except Exception:
            pass

    # ── public API ────────────────────────────────────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the MCP tool schemas discovered at startup."""
        return self._tools

    async def close_browser(self) -> None:
        """Close the browser context gracefully so Playwright can finalize
        video and trace files before the process is terminated."""
        tool_names = {t["name"] for t in self._tools}
        if "browser_close" in tool_names:
            try:
                await self.call_tool("browser_close", {})
                logger.info("Browser closed gracefully")
            except Exception as exc:
                logger.warning("browser_close failed: %s", exc)
        else:
            logger.warning("browser_close tool not available — recordings may be incomplete")

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """Invoke an MCP tool and return the result as a string."""
        response = await self._send_request(
            "tools/call",
            {"name": name, "arguments": args},
        )
        content = response.get("content", [])
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                else:
                    parts.append(json.dumps(item))
            else:
                parts.append(str(item))
        result = "\n".join(parts)
        if response.get("isError"):
            raise RuntimeError(f"MCP tool '{name}' returned an error: {result}")
        return result

    # ── internals ─────────────────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _write(self, message: dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        data = json.dumps(message) + "\n"
        self._proc.stdin.write(data.encode())
        await self._proc.stdin.drain()

    async def _read(self) -> dict[str, Any]:
        assert self._proc and self._proc.stdout
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                raise EOFError("MCP server closed stdout unexpectedly")
            text = line.decode().strip()
            if not text:
                continue
            return cast(dict[str, Any], json.loads(text))

    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        req_id = self._next_id()
        await self._write({
            "jsonrpc": _JSONRPC_VERSION,
            "id": req_id,
            "method": method,
            "params": params,
        })
        while True:
            msg = await self._read()
            # Skip notifications (no "id")
            if "id" not in msg:
                logger.debug("MCP notification: %s", msg.get("method"))
                continue
            if msg.get("id") != req_id:
                logger.warning("Unexpected response id %s (expected %s)", msg.get("id"), req_id)
                continue
            if "error" in msg:
                raise RuntimeError(f"MCP error: {msg['error']}")
            return cast(dict[str, Any], msg.get("result", {}))

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        await self._write({
            "jsonrpc": _JSONRPC_VERSION,
            "method": method,
            "params": params,
        })

    async def _initialize(self) -> None:
        await self._send_request(
            "initialize",
            {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "clientInfo": {"name": "openorch-consumer", "version": "1.0.0"},
                "capabilities": {},
            },
        )
        await self._send_notification("notifications/initialized", {})

    async def _list_tools(self) -> list[dict[str, Any]]:
        result = await self._send_request("tools/list", {})
        return cast(list[dict[str, Any]], result.get("tools", []))
