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
import logging
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
