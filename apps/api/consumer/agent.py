"""Agentic step executor.

Each test step (action + description) is driven by an LLM agent that
receives the step goal and uses Playwright browser tools to complete it.
"""

import logging
from typing import Any, Protocol, runtime_checkable

from consumer.llm_adapters.base import BaseLLMAdapter

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 10

# How many consecutive browser_snapshot calls without any action in between
# are allowed before the loop injects a recovery prompt.
_MAX_CONSECUTIVE_SNAPSHOTS = 2

# How many consecutive tool errors (across all tool calls in any iteration)
# are allowed before the step is aborted.  Prevents infinite error spirals
# where the LLM keeps retrying broken selectors without making progress.
_MAX_CONSECUTIVE_ERRORS = 3

# Tools that constitute a real browser interaction (as opposed to read-only
# observation tools such as browser_snapshot / browser_screenshot).
# After any of these runs, the loop automatically captures a fresh snapshot
# so the LLM always sees the up-to-date page state without having to ask.
_ACTION_TOOLS: frozenset[str] = frozenset({
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_select_option",
    "browser_hover",
    "browser_wait_for",
})

_SYSTEM_PROMPT = """\
You are a browser automation agent. You control a real web browser using Playwright tools.

══ CONTEXT ═══════════════════════════════════════════════════════════════════

The current page state is always included at the start of each task so you
never need to guess what is on screen. Start by reading it carefully.

══ STRICT WORKFLOW ════════════════════════════════════════════════════════════

1. READ THE PROVIDED PAGE STATE
   The snapshot at the bottom of the task message shows every visible element.
   Identify the element you need to interact with before calling any tool.

   ⚠ If the snapshot is empty, shows only a root node (e.g. "WebArea"), or contains
   no elements relevant to the goal, the page has not finished rendering. You MUST
   call browser_wait_for (with no arguments, to wait for network idle) and then call
   browser_snapshot again before attempting any action. Do NOT act on an empty snapshot.

2. CONVERT THE SNAPSHOT TO A SELECTOR
   Snapshot elements are listed as:  <role> "<name>"
   Convert them to Playwright ARIA selectors EXACTLY like this:
     combobox "Search"          →  role=combobox[name='Search']
     button "Google Search"     →  role=button[name='Google Search']
     button "Submit"            →  role=button[name='Submit']
     textbox "Email address"    →  role=textbox[name='Email address']
     link "Sign in"             →  role=link[name='Sign in']
     checkbox "Remember me"     →  role=checkbox[name='Remember me']

   ⚠ NEVER copy snapshot notation directly as a selector.
     WRONG:  link "About"
     WRONG:  button[name=Submit]
     CORRECT: role=link[name='About']
     CORRECT: role=button[name='Submit']

3. ACT
   Call the appropriate tool with the selector you derived from the snapshot.

4. VERIFY
   Call browser_snapshot again. Confirm the action had the expected effect:
   the field now contains the text, the page changed, the element is gone, etc.
   If the snapshot shows no change, the action FAILED — go to step 5.

5. RETRY ON FAILURE
   If a tool returns an ERROR or the snapshot shows no change:
   • Re-read the most recent snapshot.
   • Choose a different selector for the same element.
   • Try at most 3 different selectors before declaring the step failed.
   • NEVER repeat the exact same call that just failed.
   • If all 3 selectors fail, or the required element is simply not on the page,
     call step_failed with a clear reason — do NOT silently stop.

6. COMPLETE
   Only stop making tool calls once the snapshot confirms the goal is achieved.
   A plain-text summary with NO tool calls signals completion.

══ HARD RULES ════════════════════════════════════════════════════════════════

• Do NOT stop after a tool returns an ERROR. That is not completion — retry.
• Do NOT call browser_snapshot more than twice in a row without acting.
• Do NOT declare success if the last snapshot still shows the pre-action state.
• Do NOT use CSS classes, IDs, or XPath. ARIA role selectors are always preferred.
• Always quote the name with single quotes: role=button[name='Submit']
• Do NOT declare completion without having called at least one action tool
  (browser_click, browser_type, browser_navigate, etc.). A plain-text response
  is only valid AFTER an action has been performed and verified.
• NEVER call browser_navigate to recover from a failed action or selector error.
  Navigation destroys the current page state and cannot be undone within a step.
  If you cannot complete the step on the current page, call step_failed instead.
• Call step_failed only when the goal is genuinely impossible — not after a single error.
  Valid reasons to call step_failed:
    - The snapshot is empty after waiting for network idle and retrying.
    - The required element is not present in the snapshot and cannot be navigated to.
    - Three different selectors all timed out or errored for the same element.
    - The page is in an unexpected state that makes this step impossible to complete.
"""

_SNAPSHOT_LOOP_REMINDER = (
    "You have called browser_snapshot multiple times without performing any action. "
    "Use the snapshot information you already have — convert the element you need "
    "to a role selector (e.g. role=button[name='Submit']) and call the appropriate tool now."
)

# A synthetic tool injected into every agent loop. The LLM calls this to
# explicitly signal that the step cannot be completed, providing a reason.
# It is handled entirely within the loop and never forwarded to the browser.
_STEP_FAILED_TOOL: dict[str, Any] = {
    "name": "step_failed",
    "description": (
        "Report that this step cannot be completed. Call this tool when you have "
        "exhausted all reasonable attempts and the goal is genuinely impossible — "
        "for example, when the required element is not on the page or three different "
        "selectors have all failed. Provide a clear, specific reason so the test "
        "report is useful. Do NOT call this after a single error; retry first."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": (
                    "A clear explanation of why the step cannot be completed. "
                    "Include what was attempted and what was observed."
                ),
            }
        },
        "required": ["reason"],
    },
}


@runtime_checkable
class BrowserToolClient(Protocol):
    """Structural interface satisfied by both PlaywrightService and MCPClient.

    Any object that implements list_tools() and call_tool() can be used as
    the browser driver without inheriting from a common base class.
    """

    def list_tools(self) -> list[dict[str, Any]]: ...

    async def call_tool(self, name: str, args: dict[str, Any]) -> str: ...


async def run_step(
    browser: BrowserToolClient,
    llm: BaseLLMAdapter,
    action: str,
    description: str,
) -> dict[str, Any]:
    """Drive a single test step via the LLM agent loop.

    Before the loop starts, the current page state is captured and embedded
    directly in the user message so the LLM always has accurate context —
    it never needs to guess or infer state from a previous step.

    Args:
        browser:     Active browser tool client (PlaywrightService or MCPClient).
        llm:         LLM adapter for reasoning and tool selection.
        action:      Step action name (e.g. "click", "goto").
        description: Human-readable goal for this step.

    Returns:
        Dict with keys: action, description, status, tool_calls_made, error.
    """
    # Inject the step_failed meta-tool so the LLM can explicitly signal
    # that a step is impossible. It is handled in-loop, never sent to the browser.
    mcp_tools = [_STEP_FAILED_TOOL, *browser.list_tools()]
    tool_calls_made: list[dict[str, Any]] = []
    error: str | None = None

    # ── Pre-flight snapshot ────────────────────────────────────────────────────
    # Capture the current page state before the LLM sees the task. This grounds
    # the agent in reality and prevents silent passes where the LLM assumes a
    # previous step already completed the current goal.
    try:
        page_state = await browser.call_tool("browser_snapshot", {})
    except Exception as exc:
        logger.warning("Pre-flight snapshot failed for step '%s': %s", action, exc)
        page_state = "(page state unavailable)"

    tool_calls_made.append({"name": "browser_snapshot", "args": {}, "result": page_state})

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Action: {action}\n"
                f"Goal: {description}\n\n"
                f"Current page state:\n{page_state}"
            ),
        },
    ]

    # Tracks consecutive browser_snapshot calls with no action between them.
    consecutive_snapshots = 0
    # Tracks consecutive tool calls that returned an ERROR string.
    consecutive_errors = 0
    last_error_text = ""

    try:
        for iteration in range(_MAX_ITERATIONS):
            response = await llm.chat(messages, mcp_tools)

            if not response["tool_calls"]:
                # The LLM must have initiated at least one tool call beyond the
                # pre-flight snapshot before declaring a step complete.
                # tool_calls_made[0] is always the pre-flight, so anything at
                # index 1+ means the LLM actively worked on the step.
                if len(tool_calls_made) <= 1:
                    error = (
                        "Step completed with no browser action performed. "
                        "The agent declared success without calling any browser tool."
                    )
                    logger.warning("Step '%s' had no LLM tool calls — marking failed", action)
                else:
                    logger.info(
                        "Step '%s' completed after %d iteration(s)", action, iteration + 1
                    )
                break

            # Detect snapshot loops and inject a recovery prompt before continuing.
            tool_names = [tc["name"] for tc in response["tool_calls"]]
            if all(name == "browser_snapshot" for name in tool_names):
                consecutive_snapshots += 1
            else:
                consecutive_snapshots = 0

            if consecutive_snapshots >= _MAX_CONSECUTIVE_SNAPSHOTS:
                logger.warning(
                    "Step '%s': snapshot loop detected at iteration %d — injecting reminder",
                    action,
                    iteration,
                )
                messages.append({"role": "user", "content": _SNAPSHOT_LOOP_REMINDER})
                consecutive_snapshots = 0
                continue

            # Append the assistant turn with its tool calls.
            messages.append({
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["args"]},
                    }
                    for tc in response["tool_calls"]
                ],
            })

            # Execute each tool call and feed results back to the LLM.
            tool_results: list[dict[str, Any]] = []
            step_explicitly_failed = False
            for tc in response["tool_calls"]:
                logger.debug("Tool call: %s args=%s", tc["name"], tc["args"])

                # Handle the step_failed meta-tool without forwarding to the browser.
                if tc["name"] == "step_failed":
                    reason = tc["args"].get("reason", "No reason provided")
                    error = f"Step explicitly failed: {reason}"
                    logger.warning("Step '%s' explicitly failed: %s", action, reason)
                    tool_calls_made.append({
                        "name": tc["name"],
                        "args": tc["args"],
                        "result": "acknowledged",
                    })
                    step_explicitly_failed = True
                    break

                try:
                    result_text = await browser.call_tool(tc["name"], tc["args"])
                except Exception as exc:
                    result_text = f"ERROR: {exc}"
                    logger.warning("Tool %s failed: %s", tc["name"], exc)

                if result_text.startswith("ERROR:"):
                    consecutive_errors += 1
                    last_error_text = result_text
                else:
                    consecutive_errors = 0
                    last_error_text = ""

                tool_calls_made.append({
                    "name": tc["name"],
                    "args": tc["args"],
                    "result": result_text,
                })
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_text,
                })

            if step_explicitly_failed:
                break

            # Abort early if the LLM is stuck in an error spiral.
            if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                error = (
                    f"Step aborted after {_MAX_CONSECUTIVE_ERRORS} consecutive tool errors. "
                    f"Last error: {last_error_text}"
                )
                logger.warning(
                    "Step '%s' aborted after %d consecutive errors",
                    action,
                    _MAX_CONSECUTIVE_ERRORS,
                )
                break

            messages.extend(tool_results)

            # After any real browser interaction, capture a fresh snapshot and
            # inject it as a user message so the LLM always sees the current
            # page state without needing to explicitly request one.
            if any(tc["name"] in _ACTION_TOOLS for tc in response["tool_calls"]):
                try:
                    auto_snap = await browser.call_tool("browser_snapshot", {})
                except Exception as exc:
                    auto_snap = f"(auto-snapshot failed: {exc})"
                    logger.warning("Auto-snapshot failed for step '%s': %s", action, exc)
                tool_calls_made.append({"name": "browser_snapshot", "args": {}, "result": auto_snap})
                messages.append({"role": "user", "content": f"[Page state after action]\n{auto_snap}"})
                consecutive_snapshots = 0

        else:
            error = f"Step exceeded maximum iterations ({_MAX_ITERATIONS})"
            logger.warning("Step '%s' hit max iterations", action)

    except Exception as exc:
        error = str(exc)
        logger.exception("Agent loop error for step '%s': %s", action, exc)

    return {
        "action": action,
        "description": description,
        "status": "failed" if error else "passed",
        "tool_calls_made": tool_calls_made,
        "error": error,
    }
