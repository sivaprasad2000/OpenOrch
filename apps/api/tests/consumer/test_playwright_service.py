"""Tests for consumer/playwright_service.py.

Covers tool registration (the @tool decorator + list_tools), dispatch (call_tool),
browser lifecycle (start / stop), and the implementation of every individual tool.

All tests are pure unit tests — the Playwright async API is fully mocked via
unittest.mock, so no real browser process is launched.

Naming convention: test_<subject>_<condition>_<expected_outcome>
"""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from consumer.playwright_service import (
    BrowserConfig,
    PlaywrightService,
    _MAX_SNAPSHOT_CHARS,
    _T_CLICK,
    _T_NAVIGATE,
    _T_WAIT,
    _format_ax_tree,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_ALL_TOOL_NAMES = {
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_snapshot",
    "browser_screenshot",
    "browser_select_option",
    "browser_hover",
    "browser_wait_for",
}

_TOOL_REQUIRED_PARAMS: list[tuple[str, list[str]]] = [
    ("browser_navigate", ["url"]),
    ("browser_click", ["selector"]),
    ("browser_type", ["selector", "text"]),
    ("browser_snapshot", []),
    ("browser_screenshot", []),
    ("browser_select_option", ["selector", "value"]),
    ("browser_hover", ["selector"]),
    ("browser_wait_for", []),
]

_TOOL_DEFINITION_ORDER = [
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_snapshot",
    "browser_screenshot",
    "browser_select_option",
    "browser_hover",
    "browser_wait_for",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_page() -> MagicMock:
    """Fully-mocked Playwright Page with all tool-relevant methods as AsyncMocks."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.type = AsyncMock()
    page.select_option = AsyncMock()
    page.hover = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")
    page.title = AsyncMock(return_value="Test Page")
    page.url = "https://example.com"
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value=None)
    return page


@pytest.fixture
def service(tmp_path: Path, mock_page: MagicMock) -> PlaywrightService:
    """PlaywrightService with a mock page pre-injected — no browser launch needed."""
    svc = PlaywrightService(output_dir=tmp_path / "output")
    svc._page = mock_page  # noqa: SLF001
    return svc


@pytest.fixture
def playwright_mocks() -> dict:
    """The full Playwright browser stack as a tree of AsyncMocks.

    Tests that need to call start() / stop() should patch
    ``playwright.async_api.async_playwright`` with ``playwright_mocks["pw_cm"]``.
    """
    page = MagicMock()
    page.title = AsyncMock(return_value="Test Page")

    tracing = MagicMock()
    tracing.start = AsyncMock()
    tracing.stop = AsyncMock()

    context = MagicMock()
    context.tracing = tracing
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()

    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)

    pw = MagicMock()
    pw.chromium = chromium
    pw.stop = AsyncMock()

    pw_cm = MagicMock()
    pw_cm.start = AsyncMock(return_value=pw)

    return {
        "pw_cm": pw_cm,
        "playwright": pw,
        "chromium": chromium,
        "browser": browser,
        "context": context,
        "tracing": tracing,
        "page": page,
    }


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


async def test_list_tools_returns_all_tools(service: PlaywrightService) -> None:
    assert {t["name"] for t in service.list_tools()} == _ALL_TOOL_NAMES


async def test_list_tools_count_is_exact(service: PlaywrightService) -> None:
    assert len(service.list_tools()) == len(_ALL_TOOL_NAMES)


async def test_list_tools_preserves_definition_order(service: PlaywrightService) -> None:
    assert [t["name"] for t in service.list_tools()] == _TOOL_DEFINITION_ORDER


async def test_every_schema_has_name_description_input_schema(service: PlaywrightService) -> None:
    for schema in service.list_tools():
        assert "name" in schema
        assert "description" in schema
        assert "inputSchema" in schema


async def test_every_input_schema_is_valid_object_type(service: PlaywrightService) -> None:
    for schema in service.list_tools():
        ischema = schema["inputSchema"]
        assert ischema["type"] == "object"
        assert isinstance(ischema["properties"], dict)
        assert isinstance(ischema["required"], list)


async def test_descriptions_are_non_empty_strings(service: PlaywrightService) -> None:
    for schema in service.list_tools():
        assert isinstance(schema["description"], str)
        assert len(schema["description"]) > 0


@pytest.mark.parametrize("tool_name,expected_required", _TOOL_REQUIRED_PARAMS)
async def test_required_params_match_spec(
    service: PlaywrightService,
    tool_name: str,
    expected_required: list[str],
) -> None:
    schema = next(t for t in service.list_tools() if t["name"] == tool_name)
    assert schema["inputSchema"]["required"] == expected_required


async def test_dispatch_table_and_schemas_are_in_sync(service: PlaywrightService) -> None:
    """Every registered schema must have a handler and vice-versa."""
    schema_names = {t["name"] for t in service.list_tools()}
    dispatch_names = set(service._dispatch.keys())  # noqa: SLF001
    assert schema_names == dispatch_names


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


async def test_call_tool_unknown_name_raises_value_error(service: PlaywrightService) -> None:
    with pytest.raises(ValueError, match="Unknown browser tool"):
        await service.call_tool("browser_explode", {})


async def test_call_tool_error_message_lists_available_tools(service: PlaywrightService) -> None:
    with pytest.raises(ValueError) as exc_info:
        await service.call_tool("not_a_tool", {})
    for name in _ALL_TOOL_NAMES:
        assert name in str(exc_info.value)


async def test_call_tool_before_start_raises_runtime_error(tmp_path: Path) -> None:
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with pytest.raises(RuntimeError, match="start()"):
        await svc.call_tool("browser_navigate", {"url": "https://example.com"})


async def test_call_tool_routes_to_correct_handler(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_navigate", {"url": "https://example.com"})
    mock_page.goto.assert_awaited_once()


# ---------------------------------------------------------------------------
# Lifecycle — start()
# ---------------------------------------------------------------------------


async def test_start_creates_video_and_trace_directories(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    output = tmp_path / "run"
    svc = PlaywrightService(output_dir=output)
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    assert (output / "videos").is_dir()
    assert (output / "traces").is_dir()


async def test_start_launches_chromium_with_headless_and_slow_mo(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    cfg = BrowserConfig(headless=False, slow_mo=75)
    svc = PlaywrightService(output_dir=tmp_path / "run", config=cfg)
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    playwright_mocks["chromium"].launch.assert_awaited_once_with(
        headless=False,
        slow_mo=75,
        args=["--disable-gpu", "--no-sandbox"],
    )


async def test_start_passes_required_chromium_args(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    _, kwargs = playwright_mocks["chromium"].launch.call_args
    assert "--disable-gpu" in kwargs["args"]
    assert "--no-sandbox" in kwargs["args"]


async def test_start_creates_context_with_correct_viewport(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    cfg = BrowserConfig(viewport_width=1920, viewport_height=1080)
    svc = PlaywrightService(output_dir=tmp_path / "run", config=cfg)
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    playwright_mocks["browser"].new_context.assert_awaited_once_with(
        record_video_dir=str(tmp_path / "run" / "videos"),
        record_video_size={"width": 1920, "height": 1080},
        viewport={"width": 1920, "height": 1080},
    )


async def test_start_enables_tracing_with_screenshots_and_snapshots(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    playwright_mocks["tracing"].start.assert_awaited_once_with(screenshots=True, snapshots=True)


# ---------------------------------------------------------------------------
# Lifecycle — stop()
# ---------------------------------------------------------------------------


async def test_stop_finalizes_in_correct_order(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    """Critical ordering: tracing.stop → context.close → browser.close → playwright.stop."""
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()

    order_tracker = MagicMock()
    order_tracker.attach_mock(playwright_mocks["tracing"].stop, "tracing_stop")
    order_tracker.attach_mock(playwright_mocks["context"].close, "context_close")
    order_tracker.attach_mock(playwright_mocks["browser"].close, "browser_close")
    order_tracker.attach_mock(playwright_mocks["playwright"].stop, "playwright_stop")

    await svc.stop()

    assert order_tracker.mock_calls == [
        call.tracing_stop(path=str(tmp_path / "run" / "traces" / "trace.zip")),
        call.context_close(),
        call.browser_close(),
        call.playwright_stop(),
    ]


async def test_stop_saves_trace_to_expected_path(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    await svc.stop()
    playwright_mocks["tracing"].stop.assert_awaited_once_with(
        path=str(tmp_path / "run" / "traces" / "trace.zip")
    )


async def test_stop_is_idempotent(tmp_path: Path, playwright_mocks: dict) -> None:
    """Calling stop() twice must not raise."""
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    await svc.stop()
    await svc.stop()


async def test_stop_continues_shutdown_if_tracing_fails(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    """A tracing failure must not prevent the browser from being closed."""
    playwright_mocks["tracing"].stop.side_effect = OSError("disk full")
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    await svc.stop()
    playwright_mocks["context"].close.assert_awaited_once()
    playwright_mocks["browser"].close.assert_awaited_once()
    playwright_mocks["playwright"].stop.assert_awaited_once()


async def test_stop_clears_internal_references(
    tmp_path: Path,
    playwright_mocks: dict,
) -> None:
    svc = PlaywrightService(output_dir=tmp_path / "run")
    with patch("playwright.async_api.async_playwright", return_value=playwright_mocks["pw_cm"]):
        await svc.start()
    await svc.stop()
    assert svc._context is None  # noqa: SLF001
    assert svc._browser is None  # noqa: SLF001
    assert svc._playwright is None  # noqa: SLF001
    assert svc._page is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# browser_navigate
# ---------------------------------------------------------------------------


async def test_navigate_calls_goto_with_url(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_navigate", {"url": "https://example.com/login"})
    mock_page.goto.assert_awaited_once_with(
        "https://example.com/login",
        wait_until="domcontentloaded",
        timeout=_T_NAVIGATE,
    )


async def test_navigate_returns_confirmation_containing_url(service: PlaywrightService) -> None:
    result = await service.call_tool("browser_navigate", {"url": "https://example.com"})
    assert "https://example.com" in result


# ---------------------------------------------------------------------------
# browser_click
# ---------------------------------------------------------------------------


async def test_click_uses_default_timeout(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_click", {"selector": "role=button[name='Submit']"})
    mock_page.click.assert_awaited_once_with("role=button[name='Submit']", timeout=_T_CLICK)


async def test_click_respects_custom_timeout(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_click", {"selector": "#btn", "timeout": 15_000})
    mock_page.click.assert_awaited_once_with("#btn", timeout=15_000)


async def test_click_returns_confirmation_containing_selector(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool("browser_click", {"selector": "#submit"})
    assert "#submit" in result


# ---------------------------------------------------------------------------
# browser_type
# ---------------------------------------------------------------------------


async def test_type_uses_fill_by_default(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_type", {"selector": "#email", "text": "user@example.com"})
    mock_page.fill.assert_awaited_once_with("#email", "user@example.com")
    mock_page.type.assert_not_awaited()


async def test_type_uses_fill_when_clear_first_is_true(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool(
        "browser_type", {"selector": "#name", "text": "Alice", "clear_first": True}
    )
    mock_page.fill.assert_awaited_once_with("#name", "Alice")
    mock_page.type.assert_not_awaited()


async def test_type_uses_type_when_clear_first_is_false(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool(
        "browser_type", {"selector": "#search", "text": " extra", "clear_first": False}
    )
    mock_page.type.assert_awaited_once_with("#search", " extra")
    mock_page.fill.assert_not_awaited()


async def test_type_returns_confirmation_containing_selector(service: PlaywrightService) -> None:
    result = await service.call_tool("browser_type", {"selector": "#q", "text": "hello"})
    assert "#q" in result


# ---------------------------------------------------------------------------
# browser_snapshot
# ---------------------------------------------------------------------------


async def test_snapshot_returns_formatted_accessibility_tree(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    mock_page.accessibility.snapshot.return_value = {
        "role": "WebArea",
        "name": "Dashboard",
        "children": [
            {"role": "heading", "name": "Welcome"},
            {"role": "button", "name": "Log out"},
        ],
    }
    result = await service.call_tool("browser_snapshot", {})
    assert 'WebArea "Dashboard"' in result
    assert 'heading "Welcome"' in result
    assert 'button "Log out"' in result


async def test_snapshot_indents_children(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    mock_page.accessibility.snapshot.return_value = {
        "role": "WebArea",
        "name": "Root",
        "children": [{"role": "button", "name": "Go"}],
    }
    result = await service.call_tool("browser_snapshot", {})
    lines = result.splitlines()
    assert lines[0].startswith("WebArea")
    assert lines[1].startswith("  button")


async def test_snapshot_falls_back_when_accessibility_tree_is_none(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    mock_page.accessibility.snapshot.return_value = None
    mock_page.title.return_value = "Error Page"
    mock_page.url = "https://example.com/500"
    result = await service.call_tool("browser_snapshot", {})
    assert "Error Page" in result
    assert "https://example.com/500" in result


async def test_snapshot_truncates_at_max_chars(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    mock_page.accessibility.snapshot.return_value = {
        "role": "WebArea",
        "name": "x" * _MAX_SNAPSHOT_CHARS,
        "children": [],
    }
    result = await service.call_tool("browser_snapshot", {})
    assert result.endswith("... (truncated)")
    assert len(result) <= _MAX_SNAPSHOT_CHARS + len("\n... (truncated)")


# ---------------------------------------------------------------------------
# browser_screenshot
# ---------------------------------------------------------------------------


async def test_screenshot_returns_base64_png_data_uri(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    mock_page.screenshot.return_value = png_bytes
    result = await service.call_tool("browser_screenshot", {})
    assert result.startswith("data:image/png;base64,")
    encoded = result.removeprefix("data:image/png;base64,")
    assert base64.b64decode(encoded) == png_bytes


async def test_screenshot_captures_viewport_by_default(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_screenshot", {})
    mock_page.screenshot.assert_awaited_once_with(full_page=False, type="png")


async def test_screenshot_captures_full_page_when_requested(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_screenshot", {"full_page": True})
    mock_page.screenshot.assert_awaited_once_with(full_page=True, type="png")


async def test_screenshot_always_uses_png_format(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_screenshot", {})
    _, kwargs = mock_page.screenshot.call_args
    assert kwargs["type"] == "png"


# ---------------------------------------------------------------------------
# browser_select_option
# ---------------------------------------------------------------------------


async def test_select_option_passes_value_to_playwright(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool(
        "browser_select_option", {"selector": "#country", "value": "Canada"}
    )
    mock_page.select_option.assert_awaited_once_with("#country", value="Canada")


async def test_select_option_returns_confirmation_with_value_and_selector(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool(
        "browser_select_option", {"selector": "#size", "value": "Large"}
    )
    assert "Large" in result
    assert "#size" in result


# ---------------------------------------------------------------------------
# browser_hover
# ---------------------------------------------------------------------------


async def test_hover_calls_playwright_hover(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_hover", {"selector": ".tooltip-trigger"})
    mock_page.hover.assert_awaited_once_with(".tooltip-trigger")


async def test_hover_returns_confirmation_containing_selector(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool("browser_hover", {"selector": "#menu-item"})
    assert "#menu-item" in result


# ---------------------------------------------------------------------------
# browser_wait_for
# ---------------------------------------------------------------------------


async def test_wait_for_selector_waits_for_element(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_wait_for", {"selector": ".success-banner"})
    mock_page.wait_for_selector.assert_awaited_once_with(".success-banner", timeout=_T_WAIT)
    mock_page.wait_for_load_state.assert_not_awaited()


async def test_wait_for_text_wraps_in_text_selector(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_wait_for", {"text": "Order confirmed"})
    mock_page.wait_for_selector.assert_awaited_once_with(
        "text=Order confirmed", timeout=_T_WAIT
    )
    mock_page.wait_for_load_state.assert_not_awaited()


async def test_wait_for_no_args_waits_for_network_idle(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_wait_for", {})
    mock_page.wait_for_load_state.assert_awaited_once_with("networkidle", timeout=_T_WAIT)
    mock_page.wait_for_selector.assert_not_awaited()


async def test_wait_for_selector_takes_precedence_over_text(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_wait_for", {"selector": ".banner", "text": "Done"})
    mock_page.wait_for_selector.assert_awaited_once_with(".banner", timeout=_T_WAIT)
    mock_page.wait_for_load_state.assert_not_awaited()


async def test_wait_for_respects_custom_timeout(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    await service.call_tool("browser_wait_for", {"selector": "#slow", "timeout": 60_000})
    mock_page.wait_for_selector.assert_awaited_once_with("#slow", timeout=60_000)


async def test_wait_for_selector_returns_element_visible_confirmation(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool("browser_wait_for", {"selector": ".toast"})
    assert ".toast" in result


async def test_wait_for_text_returns_text_visible_confirmation(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool("browser_wait_for", {"text": "Payment successful"})
    assert "Payment successful" in result


async def test_wait_for_network_idle_returns_network_idle_confirmation(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool("browser_wait_for", {})
    assert "network idle" in result.lower()


# ---------------------------------------------------------------------------
# _format_ax_tree
# ---------------------------------------------------------------------------


def test_format_ax_tree_single_node() -> None:
    result = _format_ax_tree({"role": "button", "name": "Submit"})
    assert result == 'button "Submit"'


def test_format_ax_tree_indents_children() -> None:
    tree = {
        "role": "WebArea",
        "name": "Page",
        "children": [
            {"role": "heading", "name": "Title"},
            {"role": "button", "name": "OK"},
        ],
    }
    lines = _format_ax_tree(tree).splitlines()
    assert lines[0] == 'WebArea "Page"'
    assert lines[1] == '  heading "Title"'
    assert lines[2] == '  button "OK"'


def test_format_ax_tree_deep_nesting_indentation() -> None:
    tree = {
        "role": "A",
        "name": "1",
        "children": [{"role": "B", "name": "2", "children": [{"role": "C", "name": "3"}]}],
    }
    lines = _format_ax_tree(tree).splitlines()
    assert lines[0].startswith("A")
    assert lines[1].startswith("  B")
    assert lines[2].startswith("    C")


def test_format_ax_tree_includes_checked_state() -> None:
    result = _format_ax_tree({"role": "checkbox", "name": "Agree", "checked": True})
    assert "checked=True" in result


def test_format_ax_tree_includes_unchecked_state() -> None:
    result = _format_ax_tree({"role": "checkbox", "name": "Terms", "checked": False})
    assert "checked=False" in result


def test_format_ax_tree_includes_disabled_flag() -> None:
    result = _format_ax_tree({"role": "button", "name": "Save", "disabled": True})
    assert "disabled" in result


def test_format_ax_tree_includes_required_flag() -> None:
    result = _format_ax_tree({"role": "textbox", "name": "Email", "required": True})
    assert "required" in result


def test_format_ax_tree_includes_selected_flag() -> None:
    result = _format_ax_tree({"role": "option", "name": "Red", "selected": True})
    assert "selected" in result


def test_format_ax_tree_includes_heading_level() -> None:
    result = _format_ax_tree({"role": "heading", "name": "Section", "level": 2})
    assert "level=2" in result


def test_format_ax_tree_includes_expanded_state() -> None:
    result = _format_ax_tree({"role": "treeitem", "name": "Node", "expanded": False})
    assert "expanded=False" in result


def test_format_ax_tree_includes_value_text() -> None:
    result = _format_ax_tree({"role": "slider", "name": "Volume", "valuetext": "75%"})
    assert "value='75%'" in result


def test_format_ax_tree_omits_bracket_extras_when_none_present() -> None:
    result = _format_ax_tree({"role": "link", "name": "Home"})
    assert "[" not in result


def test_format_ax_tree_handles_empty_node() -> None:
    result = _format_ax_tree({})
    assert result == ' ""'


def test_format_ax_tree_handles_node_with_no_children_key() -> None:
    result = _format_ax_tree({"role": "paragraph", "name": "Hello"})
    assert result == 'paragraph "Hello"'


# ---------------------------------------------------------------------------
# _format_ax_tree — description field
# ---------------------------------------------------------------------------


def test_format_ax_tree_includes_description_when_present() -> None:
    result = _format_ax_tree({"role": "textbox", "name": "••••••••", "description": "Password"})
    assert "description='Password'" in result


def test_format_ax_tree_omits_description_when_absent() -> None:
    result = _format_ax_tree({"role": "textbox", "name": "Email"})
    assert "description" not in result


def test_format_ax_tree_includes_description_for_any_node_type() -> None:
    result = _format_ax_tree({"role": "button", "name": "X", "description": "Close dialog"})
    assert "description='Close dialog'" in result


async def test_snapshot_includes_description_from_accessibility_tree(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    mock_page.accessibility.snapshot.return_value = {
        "role": "WebArea",
        "name": "Sign In",
        "children": [
            {"role": "textbox", "name": "Email"},
            {"role": "textbox", "name": "••••••••", "description": "Password"},
        ],
    }
    result = await service.call_tool("browser_snapshot", {})
    assert "description='Password'" in result


# ---------------------------------------------------------------------------
# call_tool — required argument validation
# ---------------------------------------------------------------------------


async def test_call_tool_returns_error_string_for_missing_required_arg(
    service: PlaywrightService,
) -> None:
    """Missing 'selector' on browser_click must produce an ERROR string, not an exception."""
    result = await service.call_tool("browser_click", {})
    assert result.startswith("ERROR:")


async def test_call_tool_missing_arg_error_names_the_missing_field(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool("browser_click", {})
    assert "selector" in result


async def test_call_tool_missing_arg_error_names_the_tool(
    service: PlaywrightService,
) -> None:
    result = await service.call_tool("browser_click", {})
    assert "browser_click" in result


async def test_call_tool_does_not_raise_for_missing_required_args(
    service: PlaywrightService,
) -> None:
    """Validation must return a string, never raise."""
    try:
        result = await service.call_tool("browser_type", {})
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"call_tool raised unexpectedly: {exc}")
    assert isinstance(result, str)


async def test_call_tool_returns_error_for_partial_required_args(
    service: PlaywrightService,
) -> None:
    """browser_type requires both 'selector' and 'text'; supplying only one must error."""
    result = await service.call_tool("browser_type", {"selector": "#email"})
    assert result.startswith("ERROR:")
    assert "text" in result


async def test_call_tool_succeeds_when_all_required_args_present(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    result = await service.call_tool("browser_click", {"selector": "role=button[name='OK']"})
    assert not result.startswith("ERROR:")


async def test_call_tool_tools_with_no_required_args_never_error_on_empty_dict(
    service: PlaywrightService,
    mock_page: MagicMock,
) -> None:
    """browser_snapshot has no required args — an empty dict must always succeed."""
    mock_page.accessibility.snapshot.return_value = None
    mock_page.title.return_value = "Test"
    result = await service.call_tool("browser_snapshot", {})
    assert not result.startswith("ERROR:")
