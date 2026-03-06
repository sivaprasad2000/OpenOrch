"""In-process Playwright browser automation service.

Replaces subprocess-based MCP clients with direct playwright-python calls,
giving full control over browser context lifecycle and ensuring video and
trace files are fully finalized (seekable, complete) when stop() returns.

Public API — list_tools() / call_tool() — is intentionally identical to
MCPClient so agent.py requires no changes.

Adding a new browser tool requires only two things:
  1. Define an async method prefixed with ``_browser_``.
  2. Decorate it with ``@tool(description=..., input_schema=...)``.
The method is automatically registered in the dispatch table and its schema
is included in list_tools() — no other wiring needed.
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Chromium flags required for reliable headless operation in containers.
#:   --disable-gpu  forces software rendering so video stays non-white in headless mode
#:   --no-sandbox   required inside Docker / unprivileged CI environments
_CHROMIUM_ARGS: list[str] = ["--disable-gpu", "--no-sandbox"]

_MAX_SNAPSHOT_CHARS: int = 8_000

# Default timeouts in milliseconds — callers may override via tool arguments
_T_NAVIGATE: int = 30_000
_T_CLICK: int = 5_000
_T_WAIT: int = 10_000

_F = TypeVar("_F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------


def tool(description: str, input_schema: dict[str, Any]) -> Callable[[_F], _F]:
    """Mark a method as a browser tool and attach its MCP-compatible schema.

    The method name determines the tool name: leading underscores are stripped,
    so ``_browser_navigate`` becomes the tool ``"browser_navigate"``.

    Usage::

        @tool(
            description="Navigate the browser to a URL.",
            input_schema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        )
        async def _browser_navigate(self, args: dict[str, Any]) -> str:
            ...
    """

    def decorator(fn: _F) -> _F:
        fn._tool_schema = {  # type: ignore[attr-defined]
            "name": fn.__name__.lstrip("_"),
            "description": description,
            "inputSchema": input_schema,
        }
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Browser configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrowserConfig:
    """Immutable configuration for a single Playwright browser session.

    Attributes:
        viewport_width:  Browser viewport and video recording width in pixels.
        viewport_height: Browser viewport and video recording height in pixels.
        headless:        Run without a visible window (set False to debug locally).
        slow_mo:         Delay between every action in ms; 0 = full speed.
    """

    viewport_width: int = 1280
    viewport_height: int = 720
    headless: bool = True
    slow_mo: int = 0

    @property
    def viewport_size(self) -> dict[str, int]:
        """Playwright-compatible ``viewport`` / ``record_video_size`` mapping."""
        return {"width": self.viewport_width, "height": self.viewport_height}


# ---------------------------------------------------------------------------
# Accessibility tree formatter
# ---------------------------------------------------------------------------


def _format_ax_tree(node: dict[str, Any], indent: int = 0) -> str:
    """Recursively format a Playwright accessibility snapshot as indented text."""
    role = node.get("role", "")
    name = node.get("name", "")
    line = "  " * indent + f'{role} "{name}"'

    extras: list[str] = []
    if node.get("description"):
        extras.append(f"description={node['description']!r}")
    if node.get("level"):
        extras.append(f"level={node['level']}")
    if node.get("checked") is not None:
        extras.append(f"checked={node['checked']}")
    if node.get("disabled"):
        extras.append("disabled")
    if node.get("required"):
        extras.append("required")
    if node.get("selected"):
        extras.append("selected")
    if node.get("expanded") is not None:
        extras.append(f"expanded={node['expanded']}")
    if node.get("valuetext"):
        extras.append(f"value={node['valuetext']!r}")

    if extras:
        line += " [" + ", ".join(extras) + "]"

    parts = [line]
    for child in node.get("children") or []:
        parts.append(_format_ax_tree(child, indent + 1))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# PlaywrightService
# ---------------------------------------------------------------------------


class PlaywrightService:
    """Manages a Playwright browser in-process and exposes browser automation
    tools via the same list_tools() / call_tool() interface as MCPClient.

    Usage::

        config = BrowserConfig(headless=False, slow_mo=100)
        service = PlaywrightService(output_dir=Path("/tmp/run-42"), config=config)
        await service.start()
        try:
            await service.call_tool("browser_navigate", {"url": "https://example.com"})
            snapshot = await service.call_tool("browser_snapshot", {})
        finally:
            await service.stop()  # finalizes video + trace before returning
    """

    def __init__(self, output_dir: Path, config: BrowserConfig | None = None) -> None:
        self._output_dir = output_dir
        self._video_dir = output_dir / "videos"
        self._trace_dir = output_dir / "traces"
        self._config = config or BrowserConfig()

        # Playwright runtime state — populated by start(), cleared by stop()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        # Tab management — self._page always mirrors self._pages[self._active_page_idx]
        self._pages: list[Any] = []
        self._active_page_idx: int = 0

        # Recorded events — populated by per-page listeners attached in start() / _browser_tabs
        self._console_messages: list[dict[str, Any]] = []
        self._network_requests: list[dict[str, Any]] = []

        # Active network routes — populated by browser_route, cleared by browser_unroute
        self._routes: list[dict[str, Any]] = []

        # Tracing state — tracks whether a mid-session tracing segment is active
        self._tracing_active: bool = False

        # Auto-discover all @tool-decorated methods in definition order.
        # Both _dispatch and _schemas are derived from the same source so they
        # are always in sync — no separate list to maintain.
        self._dispatch: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._schemas: list[dict[str, Any]] = []

        for attr in vars(type(self)).values():
            schema = getattr(attr, "_tool_schema", None)
            if schema is not None:
                self._dispatch[schema["name"]] = getattr(self, attr.__name__)
                self._schemas.append(schema)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch the browser, create a recording context, and open a blank page.

        Output directories for video and trace are created automatically.
        """
        from playwright.async_api import async_playwright

        self._video_dir.mkdir(parents=True, exist_ok=True)
        self._trace_dir.mkdir(parents=True, exist_ok=True)

        cfg = self._config
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=cfg.headless,
            slow_mo=cfg.slow_mo,
            args=_CHROMIUM_ARGS,
        )
        self._context = await self._browser.new_context(
            record_video_dir=str(self._video_dir),
            record_video_size=cfg.viewport_size,
            viewport=cfg.viewport_size,
        )
        await self._context.tracing.start(screenshots=True, snapshots=True)
        self._page = await self._context.new_page()
        self._pages = [self._page]
        self._active_page_idx = 0
        self._attach_page_listeners(self._page)

        logger.info(
            "PlaywrightService started | headless=%s viewport=%dx%d slow_mo=%dms",
            cfg.headless,
            cfg.viewport_width,
            cfg.viewport_height,
            cfg.slow_mo,
        )

    async def stop(self) -> None:
        """Shut down the browser and finalize all recording files.

        Shutdown order is critical and must not be changed:
            1. tracing.stop()  — writes trace.zip to disk
            2. context.close() — finalizes the .webm (writes seekable index)
            3. browser.close()
            4. playwright.stop()
        """
        if self._context is not None:
            trace_path = self._trace_dir / "trace.zip"
            try:
                await self._context.tracing.stop(path=str(trace_path))
                logger.info("Trace saved → %s", trace_path)
            except Exception as exc:
                logger.warning("Trace save failed: %s", exc)

            await self._context.close()
            self._context = None
            self._page = None

        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

        logger.info("PlaywrightService stopped")

    # ── Public tool interface (matches MCPClient) ──────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        """Return all available browser tool schemas."""
        return self._schemas

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """Dispatch a named browser tool call.

        Returns a structured ``ERROR:`` string (rather than raising) when
        required arguments are missing, so the LLM receives actionable
        feedback and can retry with corrected arguments.

        Raises:
            ValueError:   If *name* does not match any registered tool.
            RuntimeError: If called before start().
        """
        handler = self._dispatch.get(name)
        if handler is None:
            raise ValueError(
                f"Unknown browser tool: {name!r}. Available: {list(self._dispatch)}"
            )

        schema = next((s for s in self._schemas if s["name"] == name), None)
        if schema:
            required: list[str] = schema["inputSchema"].get("required", [])
            missing = [field for field in required if field not in args]
            if missing:
                return (
                    f"ERROR: missing required argument(s) {missing} for tool {name!r}. "
                    f"All required fields: {required}"
                )

        return await handler(args)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _attach_page_listeners(self, page: Any) -> None:
        """Attach console and network listeners to a page so events are recorded."""

        def _on_console(msg: Any) -> None:
            self._console_messages.append(
                {
                    "type": msg.type,
                    "text": msg.text,
                    "location": f"{msg.location.get('url', '')}:{msg.location.get('lineNumber', '')}",
                }
            )

        def _on_request(request: Any) -> None:
            self._network_requests.append(
                {
                    "method": request.method,
                    "url": request.url,
                    "resource_type": request.resource_type,
                }
            )

        page.on("console", _on_console)
        page.on("request", _on_request)

    def _require_page(self) -> Page:
        """Return the active page or raise a clear error if not started."""
        if self._page is None:
            raise RuntimeError(
                "PlaywrightService has not been started — call await service.start() first."
            )
        return self._page

    # ── Tools ──────────────────────────────────────────────────────────────────

    @tool(
        description=(
            "Navigate the browser to a URL. Use this as the very first action of any test, "
            "or whenever the test requires loading a new page. Always provide a fully-qualified "
            "URL including the scheme (e.g. 'https://example.com/login'). The tool waits for "
            "the DOM to be ready before returning, but the page may still be loading dynamic "
            "content — follow up with browser_wait_for if the step requires a specific element "
            "or text to be present before proceeding."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "Fully-qualified URL to navigate to, including scheme "
                        "(e.g. 'https://example.com/dashboard')."
                    ),
                },
            },
            "required": ["url"],
        },
    )
    async def _browser_navigate(self, args: dict[str, Any]) -> str:
        url: str = args["url"]
        await self._require_page().goto(url, wait_until="domcontentloaded", timeout=_T_NAVIGATE)
        return f"Navigated to {url}"

    @tool(
        description=(
            "Click a button, link, checkbox, radio button, or any other interactive element. "
            "Use this for any action that requires a single mouse click — submitting a form via "
            "a button, following a navigation link, opening a dropdown menu, toggling a checkbox, "
            "or selecting a tab. Do NOT use this to type text (use browser_type), to choose from "
            "a <select> dropdown (use browser_select_option), or to reveal a tooltip (use "
            "browser_hover). Prefer ARIA role selectors (e.g. role=button[name='Submit']) or "
            "data-testid attributes over brittle CSS paths. The tool automatically waits for the "
            "element to be visible and enabled before clicking."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": (
                        "Element to click. Accepts CSS selectors (e.g. '#submit-btn'), "
                        "ARIA role selectors (e.g. \"role=button[name='Log in']\"), "
                        "or Playwright text selectors (e.g. \"text=Sign up\"). "
                        "Prefer role or test-id selectors over positional CSS."
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        f"Maximum time in ms to wait for the element to become clickable "
                        f"(default {_T_CLICK}). Increase for elements that appear after "
                        f"animations or async data loads."
                    ),
                },
            },
            "required": ["selector"],
        },
    )
    async def _browser_click(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        timeout: int = args.get("timeout", _T_CLICK)
        await self._require_page().click(selector, timeout=timeout)
        return f"Clicked '{selector}'"

    @tool(
        description=(
            "Type or paste text into a focused input field, textarea, or contenteditable element. "
            "Use this whenever the test must enter a value into a text-based field — login forms, "
            "search boxes, email inputs, password fields, multi-line textareas, etc. By default "
            "the field is cleared before typing, which is the correct behaviour for 'fill in this "
            "field with X'. Set clear_first=false only when the goal is to append to existing "
            "content. Do NOT use this for <select> dropdowns (use browser_select_option) or for "
            "pressing special keys like Enter or Tab — click the relevant button instead. The "
            "selector must resolve to a single editable element; if the element is not yet "
            "visible, call browser_wait_for first."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": (
                        "CSS or ARIA selector identifying the input or textarea to type into "
                        "(e.g. \"role=textbox[name='Email']\", '#password', 'textarea')."
                    ),
                },
                "text": {
                    "type": "string",
                    "description": "The exact text to enter into the field.",
                },
                "clear_first": {
                    "type": "boolean",
                    "description": (
                        "When true (default), the field is cleared before typing so the final "
                        "value equals exactly the provided text. Set to false to append to "
                        "whatever is already in the field."
                    ),
                },
            },
            "required": ["selector", "text"],
        },
    )
    async def _browser_type(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        text: str = args["text"]
        clear_first: bool = args.get("clear_first", True)
        page = self._require_page()
        if clear_first:
            await page.fill(selector, text)
        else:
            await page.type(selector, text)
        return f"Typed into '{selector}'"

    @tool(
        description=(
            "Read the accessibility tree of the current page as structured text. This is the "
            "primary tool for understanding what is on screen — call it to discover element "
            "roles, names, and states before deciding which selector to use in a subsequent "
            "action. Use it after every navigation or significant page change to orient yourself. "
            "Also use it to verify outcomes: after clicking a button or submitting a form, call "
            "browser_snapshot to confirm that the expected UI state was reached (e.g. a success "
            "banner appeared, a modal opened, a field became disabled). Prefer this over "
            "browser_screenshot when you only need to read text or locate interactive elements — "
            "it is faster and more token-efficient. Use browser_screenshot instead when you need "
            "to inspect visual layout, images, or styling that the accessibility tree does not "
            "capture."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )
    async def _browser_snapshot(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        page = self._require_page()
        snapshot = await page.accessibility.snapshot()
        if snapshot is None:
            title = await page.title()
            return f"Page: {title}\nURL: {page.url}\n(No accessibility tree available)"
        text = _format_ax_tree(snapshot)
        if len(text) > _MAX_SNAPSHOT_CHARS:
            text = text[:_MAX_SNAPSHOT_CHARS] + "\n... (truncated)"
        return text

    @tool(
        description=(
            "Capture a PNG screenshot of the current browser viewport and return it as a "
            "base64-encoded data URI. Use this when you need to verify visual output that the "
            "accessibility tree cannot represent — charts, images, canvas elements, colour-coded "
            "status indicators, or precise layout. Also useful for capturing evidence of a test "
            "failure (e.g. an error dialog or a broken layout). Do NOT use this as a substitute "
            "for browser_snapshot when you simply need to read text or find an element — the "
            "snapshot is faster and returns structured data the LLM can reason about directly. "
            "Set full_page=true to capture the entire scrollable document height rather than "
            "just the visible viewport."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": (
                        "When true, captures the entire scrollable page height rather than "
                        "just the visible viewport (default false)."
                    ),
                },
            },
            "required": [],
        },
    )
    async def _browser_screenshot(self, args: dict[str, Any]) -> str:
        full_page: bool = args.get("full_page", False)
        data: bytes = await self._require_page().screenshot(full_page=full_page, type="png")
        return "data:image/png;base64," + base64.b64encode(data).decode()

    @tool(
        description=(
            "Choose an option from a native HTML <select> dropdown element. Use this specifically "
            "and exclusively for <select> elements — it will not work on custom JavaScript "
            "dropdowns styled with divs, listboxes, or comboboxes. For those, use browser_click "
            "to open the menu, then browser_click again to pick the option. The value can be the "
            "option's visible label (e.g. 'United States') or its underlying value attribute — "
            "the visible label is usually safer. If you are unsure whether a dropdown is a native "
            "<select> or a custom component, call browser_snapshot first and look for a node "
            "with role='combobox' or role='listbox'; a native <select> typically appears as "
            "role='combobox' with children of role='option'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": (
                        "CSS selector targeting the <select> element itself "
                        "(e.g. '#country-select', \"role=combobox[name='Country']\")."
                    ),
                },
                "value": {
                    "type": "string",
                    "description": (
                        "The option to select. Can be the visible label text (e.g. 'Canada') "
                        "or the option's value attribute. Prefer the visible label."
                    ),
                },
            },
            "required": ["selector", "value"],
        },
    )
    async def _browser_select_option(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        value: str = args["value"]
        await self._require_page().select_option(selector, value=value)
        return f"Selected '{value}' in '{selector}'"

    @tool(
        description=(
            "Move the mouse cursor over an element without clicking it. Use this when the test "
            "goal specifically requires a hover interaction — revealing a tooltip, opening a "
            "hover-triggered dropdown menu, or triggering a CSS :hover state change. Do NOT use "
            "this as a precursor to clicking; browser_click already handles moving to the element "
            "automatically. Also do not use this to wait for an element to appear — use "
            "browser_wait_for instead. After hovering, call browser_snapshot to confirm that the "
            "expected hover state (tooltip text, submenu, etc.) became visible."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": (
                        "CSS or ARIA selector for the element to hover over "
                        "(e.g. \"role=button[name='Help']\", '.tooltip-trigger')."
                    ),
                },
            },
            "required": ["selector"],
        },
    )
    async def _browser_hover(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        await self._require_page().hover(selector)
        return f"Hovered over '{selector}'"

    @tool(
        description=(
            "Pause execution until a specific condition is met on the page. Use this after an "
            "action that triggers an asynchronous change — a navigation, a form submission, an "
            "API call, or an animation — before attempting to interact with elements that depend "
            "on that change. There are three modes depending on the arguments provided:\n"
            "  • selector: wait until a specific element matching the selector is visible in the "
            "DOM. Use this when you know which element should appear (e.g. a success toast, a "
            "modal, a newly rendered list item).\n"
            "  • text: wait until a specific string is visible anywhere on the page. Use this "
            "when you know the expected text but not the exact element (e.g. 'Welcome back', "
            "'Order confirmed').\n"
            "  • neither: wait for the page to reach network idle (no in-flight requests for "
            "500 ms). Use this after a navigation or a heavy data load when you do not know "
            "exactly which element to watch for. Note: single-page apps that poll continuously "
            "may never reach network idle — prefer selector or text in those cases.\n"
            "selector and text are mutually exclusive; if both are provided, selector takes "
            "precedence. Increase the timeout for slow networks or heavy server-side rendering."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": (
                        "CSS or ARIA selector of the element to wait for "
                        "(e.g. \"role=alert\", '.success-banner', '#confirm-dialog'). "
                        "Mutually exclusive with text."
                    ),
                },
                "text": {
                    "type": "string",
                    "description": (
                        "Exact visible text string to wait for anywhere on the page "
                        "(e.g. 'Payment successful'). Mutually exclusive with selector."
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        f"Maximum time in ms to wait before failing (default {_T_WAIT}). "
                        f"Raise this for slow APIs or heavy page loads."
                    ),
                },
            },
            "required": [],
        },
    )
    async def _browser_wait_for(self, args: dict[str, Any]) -> str:
        selector: str | None = args.get("selector")
        text: str | None = args.get("text")
        timeout: int = args.get("timeout", _T_WAIT)
        page = self._require_page()

        if selector:
            await page.wait_for_selector(selector, timeout=timeout)
            return f"Element '{selector}' is visible"
        if text:
            await page.wait_for_selector(f"text={text}", timeout=timeout)
            return f"Text '{text}' is visible"
        await page.wait_for_load_state("networkidle", timeout=timeout)
        return "Page reached network idle"

    @tool(
        description="Close the current page.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_close(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        page = self._require_page()
        await page.close()
        self._pages = [p for p in self._pages if not p.is_closed()]
        if self._pages:
            self._active_page_idx = min(self._active_page_idx, len(self._pages) - 1)
            self._page = self._pages[self._active_page_idx]
        else:
            self._page = None
        return "Page closed"

    @tool(
        description="Return all console messages recorded since the page was loaded.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_console_messages(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        if not self._console_messages:
            return "No console messages recorded"
        return json.dumps(self._console_messages, indent=2)

    @tool(
        description=(
            "Perform a drag-and-drop from one element to another. "
            "Use this to reorder list items, move cards on a kanban board, or upload files "
            "via drag-and-drop targets."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "source_selector": {
                    "type": "string",
                    "description": "Selector for the element to drag.",
                },
                "target_selector": {
                    "type": "string",
                    "description": "Selector for the drop target.",
                },
            },
            "required": ["source_selector", "target_selector"],
        },
    )
    async def _browser_drag(self, args: dict[str, Any]) -> str:
        source: str = args["source_selector"]
        target: str = args["target_selector"]
        await self._require_page().drag_and_drop(source, target)
        return f"Dragged '{source}' to '{target}'"

    @tool(
        description=(
            "Evaluate a JavaScript expression on the page or on a specific element. "
            "Use this to read computed values, inspect DOM properties, or trigger "
            "browser-side logic that has no direct Playwright equivalent."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "JavaScript expression to evaluate (e.g. 'document.title').",
                },
                "selector": {
                    "type": "string",
                    "description": (
                        "Optional CSS selector. When provided the expression receives the "
                        "matching DOM element as its first argument "
                        "(e.g. 'el => el.textContent')."
                    ),
                },
            },
            "required": ["expression"],
        },
    )
    async def _browser_evaluate(self, args: dict[str, Any]) -> str:
        expression: str = args["expression"]
        selector: str | None = args.get("selector")
        page = self._require_page()
        if selector:
            result = await page.eval_on_selector(selector, expression)
        else:
            result = await page.evaluate(expression)
        return str(result) if result is not None else "null"

    @tool(
        description="Upload one or more files to a file-input element.",
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector targeting the <input type='file'> element.",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of absolute file paths to upload.",
                },
            },
            "required": ["selector", "paths"],
        },
    )
    async def _browser_file_upload(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        paths: list[str] = args["paths"]
        await self._require_page().set_input_files(selector, paths)
        return f"Uploaded {len(paths)} file(s) to '{selector}'"

    @tool(
        description=(
            "Fill multiple form fields in a single call. "
            "More efficient than repeated browser_type calls when populating an entire form."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "description": (
                        "Mapping of selector → value for each field to fill "
                        "(e.g. {\"#email\": \"user@example.com\", \"#password\": \"secret\"})."
                    ),
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["fields"],
        },
    )
    async def _browser_fill_form(self, args: dict[str, Any]) -> str:
        fields: dict[str, str] = args["fields"]
        page = self._require_page()
        for selector, value in fields.items():
            await page.fill(selector, value)
        return f"Filled {len(fields)} field(s)"

    @tool(
        description=(
            "Register a one-time handler for the next browser dialog (alert, confirm, or prompt). "
            "Must be called BEFORE the action that triggers the dialog."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["accept", "dismiss"],
                    "description": "Whether to accept or dismiss the dialog.",
                },
                "prompt_text": {
                    "type": "string",
                    "description": "Text to enter when accepting a prompt dialog (optional).",
                },
            },
            "required": ["action"],
        },
    )
    async def _browser_handle_dialog(self, args: dict[str, Any]) -> str:
        action: str = args["action"]
        prompt_text: str = args.get("prompt_text", "")
        page = self._require_page()

        async def _handler(dialog: Any) -> None:
            if action == "accept":
                await dialog.accept(prompt_text)
            else:
                await dialog.dismiss()

        page.once("dialog", _handler)
        return f"Dialog handler registered: will {action} next dialog"

    @tool(
        description="Go back to the previous page in the browser history.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_navigate_back(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        page = self._require_page()
        response = await page.go_back(wait_until="domcontentloaded", timeout=_T_NAVIGATE)
        if response is None:
            return "No previous page in history"
        return f"Navigated back to {page.url}"

    @tool(
        description="Return all network requests recorded since the page was loaded.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_network_requests(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        if not self._network_requests:
            return "No network requests recorded"
        return json.dumps(self._network_requests, indent=2)

    @tool(
        description=(
            "Press a keyboard key, optionally while an element is focused. "
            "Use for special keys (Enter, Tab, Escape, ArrowDown, etc.) or keyboard shortcuts "
            "(Control+A, Meta+C). For regular text input use browser_type instead."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": (
                        "Key name as understood by Playwright "
                        "(e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown', 'Control+A')."
                    ),
                },
                "selector": {
                    "type": "string",
                    "description": (
                        "Optional selector. When provided, the element is focused before "
                        "the key is pressed."
                    ),
                },
            },
            "required": ["key"],
        },
    )
    async def _browser_press_key(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        selector: str | None = args.get("selector")
        page = self._require_page()
        if selector:
            await page.press(selector, key)
        else:
            await page.keyboard.press(key)
        return f"Pressed key '{key}'"

    @tool(
        description="Resize the browser viewport to the given width and height in pixels.",
        input_schema={
            "type": "object",
            "properties": {
                "width": {"type": "integer", "description": "New viewport width in pixels."},
                "height": {"type": "integer", "description": "New viewport height in pixels."},
            },
            "required": ["width", "height"],
        },
    )
    async def _browser_resize(self, args: dict[str, Any]) -> str:
        width: int = args["width"]
        height: int = args["height"]
        await self._require_page().set_viewport_size({"width": width, "height": height})
        return f"Viewport resized to {width}x{height}"

    @tool(
        description=(
            "Run a JavaScript snippet on the page and return its result. "
            "The snippet is wrapped in an async function — use 'return' to produce a value."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "JavaScript code to execute (e.g. 'return document.title'). "
                        "Has access to the full browser environment."
                    ),
                },
            },
            "required": ["code"],
        },
    )
    async def _browser_run_code(self, args: dict[str, Any]) -> str:
        code: str = args["code"]
        result = await self._require_page().evaluate(f"async () => {{ {code} }}")
        return str(result) if result is not None else "(no return value)"

    @tool(
        description=(
            "List, create, close, or switch browser tabs. "
            "Use action='list' to see open tabs, 'create' to open a new tab, "
            "'close' to close a tab by index, and 'select' to switch the active tab."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "close", "select"],
                    "description": "Tab operation to perform (default: 'list').",
                },
                "index": {
                    "type": "integer",
                    "description": "Tab index for 'close' and 'select' actions.",
                },
                "url": {
                    "type": "string",
                    "description": "URL to navigate to immediately after creating a new tab.",
                },
            },
            "required": [],
        },
    )
    async def _browser_tabs(self, args: dict[str, Any]) -> str:
        action: str = args.get("action", "list")

        if action == "list":
            lines = [
                f"[{i}]{'*' if i == self._active_page_idx else ' '} {p.url or 'about:blank'}"
                for i, p in enumerate(self._pages)
            ]
            return "Tabs:\n" + "\n".join(lines)

        if action == "create":
            if self._context is None:
                raise RuntimeError("PlaywrightService has not been started.")
            new_page = await self._context.new_page()
            self._attach_page_listeners(new_page)
            self._pages.append(new_page)
            self._active_page_idx = len(self._pages) - 1
            self._page = new_page
            url: str | None = args.get("url")
            if url:
                await new_page.goto(url, wait_until="domcontentloaded", timeout=_T_NAVIGATE)
            return f"Created new tab [{self._active_page_idx}]"

        if action == "close":
            idx: int = args.get("index", self._active_page_idx)
            await self._pages[idx].close()
            self._pages.pop(idx)
            if self._pages:
                self._active_page_idx = min(idx, len(self._pages) - 1)
                self._page = self._pages[self._active_page_idx]
            else:
                self._page = None
            return f"Closed tab [{idx}]"

        if action == "select":
            idx = args["index"]
            self._active_page_idx = idx
            self._page = self._pages[idx]
            return f"Switched to tab [{idx}]: {self._page.url}"

        return f"Unknown tab action: {action!r}"

    @tool(
        description=(
            "Install a Playwright browser. Run this once if the target browser is not yet "
            "installed in the environment (e.g. inside a fresh Docker image)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "browser": {
                    "type": "string",
                    "enum": ["chromium", "firefox", "webkit"],
                    "description": "Browser to install (default: 'chromium').",
                },
            },
            "required": [],
        },
    )
    async def _browser_install(self, args: dict[str, Any]) -> str:
        browser: str = args.get("browser", "chromium")
        result = subprocess.run(
            ["python", "-m", "playwright", "install", browser],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return f"Browser '{browser}' installed successfully"
        return f"ERROR: {result.stderr.strip()}"

    @tool(
        description="Click the left mouse button at an exact screen coordinate.",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate in pixels."},
                "y": {"type": "number", "description": "Y coordinate in pixels."},
                "button": {
                    "type": "string",
                    "enum": ["left", "middle", "right"],
                    "description": "Mouse button to click (default: 'left').",
                },
            },
            "required": ["x", "y"],
        },
    )
    async def _browser_mouse_click_xy(self, args: dict[str, Any]) -> str:
        x: float = args["x"]
        y: float = args["y"]
        button: str = args.get("button", "left")
        await self._require_page().mouse.click(x, y, button=button)
        return f"Clicked at ({x}, {y})"

    @tool(
        description=(
            "Press and hold the mouse button at the current cursor position or at optional "
            "coordinates. Typically followed by browser_mouse_drag_xy and browser_mouse_up."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate to move to before pressing."},
                "y": {"type": "number", "description": "Y coordinate to move to before pressing."},
            },
            "required": [],
        },
    )
    async def _browser_mouse_down(self, args: dict[str, Any]) -> str:
        x: float | None = args.get("x")
        y: float | None = args.get("y")
        page = self._require_page()
        if x is not None and y is not None:
            await page.mouse.move(x, y)
        await page.mouse.down()
        return "Mouse button pressed down"

    @tool(
        description=(
            "Drag the mouse (with the button already held down) to the given target coordinates. "
            "Use after browser_mouse_down and before browser_mouse_up to perform a coordinate-based drag."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "target_x": {"type": "number", "description": "Target X coordinate in pixels."},
                "target_y": {"type": "number", "description": "Target Y coordinate in pixels."},
            },
            "required": ["target_x", "target_y"],
        },
    )
    async def _browser_mouse_drag_xy(self, args: dict[str, Any]) -> str:
        target_x: float = args["target_x"]
        target_y: float = args["target_y"]
        await self._require_page().mouse.move(target_x, target_y)
        return f"Dragged mouse to ({target_x}, {target_y})"

    @tool(
        description="Move the mouse cursor to the given screen coordinates without clicking.",
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate in pixels."},
                "y": {"type": "number", "description": "Y coordinate in pixels."},
            },
            "required": ["x", "y"],
        },
    )
    async def _browser_mouse_move_xy(self, args: dict[str, Any]) -> str:
        x: float = args["x"]
        y: float = args["y"]
        await self._require_page().mouse.move(x, y)
        return f"Mouse moved to ({x}, {y})"

    @tool(
        description=(
            "Release the mouse button at the current cursor position or at optional coordinates. "
            "Use after browser_mouse_drag_xy to complete a drag operation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate to move to before releasing."},
                "y": {"type": "number", "description": "Y coordinate to move to before releasing."},
            },
            "required": [],
        },
    )
    async def _browser_mouse_up(self, args: dict[str, Any]) -> str:
        x: float | None = args.get("x")
        y: float | None = args.get("y")
        page = self._require_page()
        if x is not None and y is not None:
            await page.mouse.move(x, y)
        await page.mouse.up()
        return "Mouse button released"

    @tool(
        description="Scroll the mouse wheel by the given pixel delta.",
        input_schema={
            "type": "object",
            "properties": {
                "delta_x": {
                    "type": "number",
                    "description": "Horizontal scroll distance in pixels (positive = right).",
                },
                "delta_y": {
                    "type": "number",
                    "description": "Vertical scroll distance in pixels (positive = down).",
                },
            },
            "required": [],
        },
    )
    async def _browser_mouse_wheel(self, args: dict[str, Any]) -> str:
        delta_x: float = args.get("delta_x", 0)
        delta_y: float = args.get("delta_y", 0)
        await self._require_page().mouse.wheel(delta_x, delta_y)
        return f"Scrolled wheel by ({delta_x}, {delta_y})"

    @tool(
        description="Save the current page as a PDF file.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Absolute file path for the PDF. "
                        "Defaults to <output_dir>/page.pdf when omitted."
                    ),
                },
            },
            "required": [],
        },
    )
    async def _browser_pdf_save(self, args: dict[str, Any]) -> str:
        path: str = args.get("path") or str(self._output_dir / "page.pdf")
        await self._require_page().pdf(path=path)
        return f"PDF saved to {path}"

    @tool(
        description=(
            "Generate the most stable Playwright locator for an element. "
            "Prefers data-testid, then ARIA role+name, then id, then tag attributes. "
            "Use the returned locator string in subsequent tool calls."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Any selector that uniquely identifies the element.",
                },
            },
            "required": ["selector"],
        },
    )
    async def _browser_generate_locator(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        locator: str = await self._require_page().eval_on_selector(
            selector,
            """el => {
                const testId = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
                if (testId) return `[data-testid="${testId}"]`;
                const role = el.getAttribute('role');
                const label = el.getAttribute('aria-label');
                if (role && label) return `role=${role}[name="${label}"]`;
                if (el.id) return `#${el.id}`;
                const tag = el.tagName.toLowerCase();
                const name = el.getAttribute('name');
                if (name) return `${tag}[name="${name}"]`;
                const ph = el.getAttribute('placeholder');
                if (ph) return `${tag}[placeholder="${ph}"]`;
                const text = el.textContent?.trim().substring(0, 40);
                if (text) return `text=${text}`;
                return tag + (el.className ? `.${el.className.split(' ')[0]}` : '');
            }""",
        )
        return f"Locator: {locator}"

    @tool(
        description="Assert that a specific element is currently visible on the page.",
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS or ARIA selector of the element to check.",
                },
            },
            "required": ["selector"],
        },
    )
    async def _browser_verify_element_visible(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        visible = await self._require_page().is_visible(selector)
        status = "PASS" if visible else "FAIL"
        return f"{status}: element '{selector}' {'is' if visible else 'is not'} visible"

    @tool(
        description=(
            "Assert that every element in a list of selectors is visible on the page. "
            "Returns a per-item PASS/FAIL report."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selectors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of CSS or ARIA selectors to check.",
                },
            },
            "required": ["selectors"],
        },
    )
    async def _browser_verify_list_visible(self, args: dict[str, Any]) -> str:
        selectors: list[str] = args["selectors"]
        page = self._require_page()
        results: list[str] = []
        all_pass = True
        for sel in selectors:
            visible = await page.is_visible(sel)
            results.append(f"{'PASS' if visible else 'FAIL'}: '{sel}'")
            if not visible:
                all_pass = False
        summary = "All elements visible" if all_pass else "Some elements not visible"
        return summary + "\n" + "\n".join(results)

    @tool(
        description="Assert that a specific text string is visible anywhere on the page.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Exact text string to look for on the page.",
                },
            },
            "required": ["text"],
        },
    )
    async def _browser_verify_text_visible(self, args: dict[str, Any]) -> str:
        text: str = args["text"]
        visible = await self._require_page().is_visible(f"text={text}")
        status = "PASS" if visible else "FAIL"
        return f"{status}: text '{text}' {'is' if visible else 'is not'} visible"

    @tool(
        description="Assert that an input element contains the expected value.",
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the input element.",
                },
                "value": {
                    "type": "string",
                    "description": "Expected value of the input.",
                },
            },
            "required": ["selector", "value"],
        },
    )
    async def _browser_verify_value(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        expected: str = args["value"]
        actual = await self._require_page().input_value(selector)
        if actual == expected:
            return f"PASS: value is '{actual}'"
        return f"FAIL: expected '{expected}' but got '{actual}'"

    # ── Navigation extras ──────────────────────────────────────────────────────

    @tool(
        description="Go forward to the next page in the browser history.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_navigate_forward(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        page = self._require_page()
        response = await page.go_forward(wait_until="domcontentloaded", timeout=_T_NAVIGATE)
        if response is None:
            return "No next page in history"
        return f"Navigated forward to {page.url}"

    @tool(
        description="Reload the current page.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_reload(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        page = self._require_page()
        await page.reload(wait_until="domcontentloaded", timeout=_T_NAVIGATE)
        return f"Page reloaded: {page.url}"

    # ── Console extras ─────────────────────────────────────────────────────────

    @tool(
        description="Clear all console messages recorded so far.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_console_clear(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        self._console_messages.clear()
        return "Console messages cleared"

    # ── Network extras ─────────────────────────────────────────────────────────

    @tool(
        description="Clear all recorded network requests.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_network_clear(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        self._network_requests.clear()
        return "Network requests cleared"

    # ── Keyboard extras ────────────────────────────────────────────────────────

    @tool(
        description=(
            "Type text character by character (key-by-key). "
            "Use this instead of browser_type when the application listens to individual "
            "keydown/keypress/keyup events rather than the input event. "
            "Optionally press Enter after typing by setting submit=true."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type character by character.",
                },
                "submit": {
                    "type": "boolean",
                    "description": "If true, press Enter after typing (default false).",
                },
            },
            "required": ["text"],
        },
    )
    async def _browser_press_sequentially(self, args: dict[str, Any]) -> str:
        text: str = args["text"]
        submit: bool = args.get("submit", False)
        page = self._require_page()
        await page.keyboard.type(text)
        if submit:
            await page.keyboard.press("Enter")
        return f"Typed sequentially: '{text}'" + (" + Enter" if submit else "")

    @tool(
        description=(
            "Hold a keyboard key down without releasing it. "
            "Use before browser_keyup to simulate modifier key combinations "
            "(e.g., hold Shift then press another key)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": (
                        "Key name as understood by Playwright "
                        "(e.g. 'Shift', 'Control', 'Alt', 'a')."
                    ),
                },
            },
            "required": ["key"],
        },
    )
    async def _browser_keydown(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        await self._require_page().keyboard.down(key)
        return f"Key '{key}' pressed down"

    @tool(
        description="Release a keyboard key that was previously held down with browser_keydown.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key name to release (e.g. 'Shift', 'Control', 'Alt').",
                },
            },
            "required": ["key"],
        },
    )
    async def _browser_keyup(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        await self._require_page().keyboard.up(key)
        return f"Key '{key}' released"

    # ── Form extras ────────────────────────────────────────────────────────────

    @tool(
        description=(
            "Check a checkbox or radio button. "
            "Use this specifically to tick a checkbox or select a radio button — "
            "it ensures the element ends up in the checked state regardless of its current state. "
            "Do NOT use browser_click for checkboxes as it toggles rather than guarantees state."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS or ARIA selector for the checkbox or radio button.",
                },
            },
            "required": ["selector"],
        },
    )
    async def _browser_check(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        await self._require_page().check(selector)
        return f"Checked '{selector}'"

    @tool(
        description=(
            "Uncheck a checkbox. "
            "Ensures the checkbox ends up in the unchecked state regardless of its current state."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS or ARIA selector for the checkbox to uncheck.",
                },
            },
            "required": ["selector"],
        },
    )
    async def _browser_uncheck(self, args: dict[str, Any]) -> str:
        selector: str = args["selector"]
        await self._require_page().uncheck(selector)
        return f"Unchecked '{selector}'"

    # ── Cookies ────────────────────────────────────────────────────────────────

    @tool(
        description="List all cookies in the current browser context, optionally filtered by domain or path.",
        input_schema={
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Filter cookies whose domain contains this string.",
                },
                "path": {
                    "type": "string",
                    "description": "Filter cookies whose path starts with this string.",
                },
            },
            "required": [],
        },
    )
    async def _browser_cookie_list(self, args: dict[str, Any]) -> str:
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        domain: str | None = args.get("domain")
        path: str | None = args.get("path")
        cookies = await self._context.cookies()
        if domain:
            cookies = [c for c in cookies if domain in c.get("domain", "")]
        if path:
            cookies = [c for c in cookies if c.get("path", "").startswith(path)]
        if not cookies:
            return "No cookies found"
        return json.dumps(cookies, indent=2)

    @tool(
        description="Get a specific cookie by name.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Cookie name to retrieve."},
            },
            "required": ["name"],
        },
    )
    async def _browser_cookie_get(self, args: dict[str, Any]) -> str:
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        name: str = args["name"]
        cookies = await self._context.cookies()
        match = next((c for c in cookies if c.get("name") == name), None)
        if match is None:
            return f"Cookie '{name}' not found"
        return json.dumps(match, indent=2)

    @tool(
        description="Set a cookie in the current browser context.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Cookie name."},
                "value": {"type": "string", "description": "Cookie value."},
                "domain": {"type": "string", "description": "Cookie domain (e.g. '.example.com')."},
                "path": {"type": "string", "description": "Cookie path (default: '/')."},
                "expires": {
                    "type": "number",
                    "description": "Expiration as a Unix timestamp in seconds. Omit for session cookie.",
                },
                "http_only": {"type": "boolean", "description": "Mark cookie as HttpOnly."},
                "secure": {"type": "boolean", "description": "Mark cookie as Secure."},
                "same_site": {
                    "type": "string",
                    "enum": ["Strict", "Lax", "None"],
                    "description": "SameSite attribute.",
                },
            },
            "required": ["name", "value"],
        },
    )
    async def _browser_cookie_set(self, args: dict[str, Any]) -> str:
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        cookie: dict[str, Any] = {
            "name": args["name"],
            "value": args["value"],
            "url": self._require_page().url or "about:blank",
        }
        if "domain" in args:
            cookie["domain"] = args["domain"]
            cookie.pop("url", None)
            cookie.setdefault("path", args.get("path", "/"))
        if "path" in args:
            cookie["path"] = args["path"]
        if "expires" in args:
            cookie["expires"] = args["expires"]
        if "http_only" in args:
            cookie["httpOnly"] = args["http_only"]
        if "secure" in args:
            cookie["secure"] = args["secure"]
        if "same_site" in args:
            cookie["sameSite"] = args["same_site"]
        await self._context.add_cookies([cookie])
        return f"Cookie '{args['name']}' set"

    @tool(
        description="Delete a specific cookie by name.",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Cookie name to delete."},
            },
            "required": ["name"],
        },
    )
    async def _browser_cookie_delete(self, args: dict[str, Any]) -> str:
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        name: str = args["name"]
        # Playwright has no delete-by-name API; clear all and re-add the rest
        all_cookies = await self._context.cookies()
        remaining = [c for c in all_cookies if c.get("name") != name]
        await self._context.clear_cookies()
        if remaining:
            await self._context.add_cookies(remaining)
        return f"Cookie '{name}' deleted"

    @tool(
        description="Clear all cookies from the current browser context.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_cookie_clear(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        await self._context.clear_cookies()
        return "All cookies cleared"

    # ── localStorage ───────────────────────────────────────────────────────────

    @tool(
        description="List all key-value pairs in localStorage for the current page origin.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_localstorage_list(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        items: dict[str, str] = await self._require_page().evaluate(
            "() => Object.fromEntries(Object.entries(localStorage))"
        )
        if not items:
            return "localStorage is empty"
        return json.dumps(items, indent=2)

    @tool(
        description="Get a localStorage item by key.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to retrieve."},
            },
            "required": ["key"],
        },
    )
    async def _browser_localstorage_get(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        value: str | None = await self._require_page().evaluate(
            f"() => localStorage.getItem({json.dumps(key)})"
        )
        if value is None:
            return f"Key '{key}' not found in localStorage"
        return value

    @tool(
        description="Set a localStorage item.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to set."},
                "value": {"type": "string", "description": "Value to set."},
            },
            "required": ["key", "value"],
        },
    )
    async def _browser_localstorage_set(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        value: str = args["value"]
        await self._require_page().evaluate(
            f"() => localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
        )
        return f"localStorage['{key}'] = '{value}'"

    @tool(
        description="Delete a localStorage item by key.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to delete."},
            },
            "required": ["key"],
        },
    )
    async def _browser_localstorage_delete(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        await self._require_page().evaluate(
            f"() => localStorage.removeItem({json.dumps(key)})"
        )
        return f"localStorage key '{key}' deleted"

    @tool(
        description="Clear all items from localStorage.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_localstorage_clear(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        await self._require_page().evaluate("() => localStorage.clear()")
        return "localStorage cleared"

    # ── sessionStorage ─────────────────────────────────────────────────────────

    @tool(
        description="List all key-value pairs in sessionStorage for the current page origin.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_sessionstorage_list(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        items: dict[str, str] = await self._require_page().evaluate(
            "() => Object.fromEntries(Object.entries(sessionStorage))"
        )
        if not items:
            return "sessionStorage is empty"
        return json.dumps(items, indent=2)

    @tool(
        description="Get a sessionStorage item by key.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to retrieve."},
            },
            "required": ["key"],
        },
    )
    async def _browser_sessionstorage_get(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        value: str | None = await self._require_page().evaluate(
            f"() => sessionStorage.getItem({json.dumps(key)})"
        )
        if value is None:
            return f"Key '{key}' not found in sessionStorage"
        return value

    @tool(
        description="Set a sessionStorage item.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to set."},
                "value": {"type": "string", "description": "Value to set."},
            },
            "required": ["key", "value"],
        },
    )
    async def _browser_sessionstorage_set(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        value: str = args["value"]
        await self._require_page().evaluate(
            f"() => sessionStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
        )
        return f"sessionStorage['{key}'] = '{value}'"

    @tool(
        description="Delete a sessionStorage item by key.",
        input_schema={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key to delete."},
            },
            "required": ["key"],
        },
    )
    async def _browser_sessionstorage_delete(self, args: dict[str, Any]) -> str:
        key: str = args["key"]
        await self._require_page().evaluate(
            f"() => sessionStorage.removeItem({json.dumps(key)})"
        )
        return f"sessionStorage key '{key}' deleted"

    @tool(
        description="Clear all items from sessionStorage.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_sessionstorage_clear(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        await self._require_page().evaluate("() => sessionStorage.clear()")
        return "sessionStorage cleared"

    # ── Storage state ──────────────────────────────────────────────────────────

    @tool(
        description=(
            "Save the full browser storage state (cookies + localStorage) to a JSON file. "
            "Use this to capture an authenticated session so it can be restored later with "
            "browser_set_storage_state, avoiding repeated logins in subsequent test runs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": (
                        "Absolute path for the output JSON file. "
                        "Defaults to <output_dir>/storage-state.json when omitted."
                    ),
                },
            },
            "required": [],
        },
    )
    async def _browser_storage_state(self, args: dict[str, Any]) -> str:
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        path: str = args.get("filename") or str(self._output_dir / "storage-state.json")
        await self._context.storage_state(path=path)
        return f"Storage state saved to {path}"

    @tool(
        description=(
            "Restore browser storage state (cookies + localStorage) from a previously saved file. "
            "This clears all existing cookies and storage before loading the saved state. "
            "Use this to skip login by restoring a session captured with browser_storage_state."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Absolute path to the storage state JSON file to restore.",
                },
            },
            "required": ["filename"],
        },
    )
    async def _browser_set_storage_state(self, args: dict[str, Any]) -> str:
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        filename: str = args["filename"]
        import json as _json
        with open(filename) as f:
            state: dict[str, Any] = _json.load(f)
        await self._context.clear_cookies()
        cookies = state.get("cookies", [])
        if cookies:
            await self._context.add_cookies(cookies)
        # Restore localStorage via page evaluation
        for origin_entry in state.get("origins", []):
            ls = origin_entry.get("localStorage", [])
            if not ls:
                continue
            page = self._require_page()
            for item in ls:
                k = json.dumps(item["name"])
                v = json.dumps(item["value"])
                await page.evaluate(f"() => localStorage.setItem({k}, {v})")
        return f"Storage state restored from {filename}"

    # ── Network routing (mocking) ──────────────────────────────────────────────

    @tool(
        description=(
            "Intercept and mock network requests matching a URL pattern. "
            "Use this to stub API responses during testing — return fixed JSON, simulate errors, "
            "or block specific resources. The pattern supports glob wildcards "
            "(e.g. '**/api/users', '**/*.{png,jpg}')."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern matching URLs to intercept (e.g. '**/api/users').",
                },
                "status": {
                    "type": "integer",
                    "description": "HTTP status code to return (default: 200).",
                },
                "body": {
                    "type": "string",
                    "description": "Response body — plain text or a JSON string.",
                },
                "content_type": {
                    "type": "string",
                    "description": "Content-Type header (e.g. 'application/json', 'text/html').",
                },
            },
            "required": ["pattern"],
        },
    )
    async def _browser_route(self, args: dict[str, Any]) -> str:
        pattern: str = args["pattern"]
        status: int = args.get("status", 200)
        body: str = args.get("body", "")
        content_type: str = args.get("content_type", "application/json")

        async def _handler(route: Any) -> None:
            await route.fulfill(status=status, body=body, content_type=content_type)

        await self._require_page().route(pattern, _handler)
        self._routes.append({"pattern": pattern, "status": status, "content_type": content_type})
        return f"Route registered: {pattern} → {status}"

    @tool(
        description="List all active network routes registered with browser_route.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_route_list(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        if not self._routes:
            return "No active routes"
        return json.dumps(self._routes, indent=2)

    @tool(
        description=(
            "Remove network route(s) registered with browser_route. "
            "Pass a pattern to remove routes matching that pattern, "
            "or omit the pattern to remove all routes."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "URL pattern to unroute. Omit to remove all routes.",
                },
            },
            "required": [],
        },
    )
    async def _browser_unroute(self, args: dict[str, Any]) -> str:
        pattern: str | None = args.get("pattern")
        page = self._require_page()
        if pattern:
            await page.unroute(pattern)
            self._routes = [r for r in self._routes if r["pattern"] != pattern]
            return f"Route removed: {pattern}"
        else:
            for r in self._routes:
                try:
                    await page.unroute(r["pattern"])
                except Exception:
                    pass
            self._routes.clear()
            return "All routes removed"

    # ── Tracing ────────────────────────────────────────────────────────────────

    @tool(
        description=(
            "Start a new Playwright trace recording segment. "
            "Use this to capture a focused trace around a specific action sequence. "
            "Stop recording with browser_stop_tracing to save the trace file."
        ),
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    async def _browser_start_tracing(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        if self._tracing_active:
            return "Tracing is already active"
        await self._context.tracing.start(screenshots=True, snapshots=True)
        self._tracing_active = True
        return "Tracing started"

    @tool(
        description=(
            "Stop the current trace recording and save it to a file. "
            "The trace can be inspected with 'playwright show-trace <path>'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Absolute file path for the trace archive (.zip). "
                        "Defaults to <output_dir>/traces/segment-trace.zip when omitted."
                    ),
                },
            },
            "required": [],
        },
    )
    async def _browser_stop_tracing(self, args: dict[str, Any]) -> str:
        if self._context is None:
            raise RuntimeError("PlaywrightService has not been started.")
        if not self._tracing_active:
            return "No active tracing session"
        path: str = args.get("path") or str(self._trace_dir / "segment-trace.zip")
        await self._context.tracing.stop(path=path)
        self._tracing_active = False
        return f"Trace saved to {path}"

    # ── Video ──────────────────────────────────────────────────────────────────

    @tool(
        description=(
            "Start a new video recording for the current page. "
            "Video is saved when browser_stop_video is called or the context closes. "
            "Note: if the context was already started with record_video_dir, "
            "this adds an additional per-page recording."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "width": {
                    "type": "integer",
                    "description": "Video width in pixels (defaults to viewport width).",
                },
                "height": {
                    "type": "integer",
                    "description": "Video height in pixels (defaults to viewport height).",
                },
            },
            "required": [],
        },
    )
    async def _browser_start_video(self, args: dict[str, Any]) -> str:
        # Playwright records video at context level; a separate context-level video
        # is already started in start(). This tool reports the current video path.
        page = self._require_page()
        video = page.video
        if video is None:
            return (
                "Video recording is not active. "
                "The context must be created with record_video_dir to enable recording."
            )
        path = await video.path()
        return f"Video recording is active → {path}"

    @tool(
        description=(
            "Stop the current video recording and save the file. "
            "Returns the path to the saved video file."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Absolute file path to save the video. "
                        "Defaults to the auto-generated path in <output_dir>/videos/."
                    ),
                },
            },
            "required": [],
        },
    )
    async def _browser_stop_video(self, args: dict[str, Any]) -> str:
        page = self._require_page()
        video = page.video
        if video is None:
            return "No video recording is active"
        save_path: str | None = args.get("path")
        if save_path:
            await video.save_as(save_path)
            return f"Video saved to {save_path}"
        path = await video.path()
        return f"Video recording will be finalized at {path} when the context closes"
