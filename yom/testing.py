"""Testing utilities for yom-agent.

Usage:
    from yom.testing import fake_agent, MockProvider, assert_response

    # Create a fake agent that returns predictable responses
    agent = fake_agent("Hello, I'm a fake agent!")

    # Or with a mock provider
    provider = MockProvider(responses=["response1", "response2"])
    agent = fake_agent(provider=provider)

    # Test the agent
    result = await agent.run("Hello")
    assert_response(result, contains="Hello")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from yom import Agent
from yom.providers import BaseProvider, LLMResponse, Message, CompletionConfig, Usage


# =============================================================================
# Mock Provider
# =============================================================================

@dataclass
class MockProvider(BaseProvider):
    """Mock LLM provider for testing."""

    responses: list[str] = field(default_factory=list)
    current_index: int = 0
    tool_call_responses: list[dict] = field(default_factory=list)
    error_on_call: int | None = None

    @property
    def provider_name(self) -> str:
        return "mock"

    async def complete(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Return a mock response."""
        if self.error_on_call is not None and self.error_on_call <= 0:
            raise RuntimeError("Mock error")

        if self.error_on_call is not None:
            self.error_on_call -= 1

        if self.current_index >= len(self.responses):
            response_text = self.responses[-1] if self.responses else "No response configured"
        else:
            response_text = self.responses[self.current_index]
            self.current_index += 1

        # Count tokens as rough estimate
        tokens = len(response_text.split()) * 2

        return LLMResponse(
            content=response_text,
            model=model,
            usage=Usage(
                input_tokens=len(" ".join(m.content for m in messages).split()) * 2,
                output_tokens=tokens,
                total_tokens=tokens * 2,
            ),
            stop_reason="stop",
            raw={},
        )

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages."""
        return [{"role": m.role, "content": m.content} for m in messages]


# =============================================================================
# Fake Agent
# =============================================================================

def fake_agent(
    response: str | list[str] = "This is a fake response.",
    tool_calls: list[dict] | None = None,
    delay: float = 0,
) -> Agent:
    """Create a fake agent that returns predictable responses.

    Args:
        response: String or list of strings for responses
        tool_calls: Optional tool calls to return
        delay: Optional delay in seconds

    Returns:
        Agent configured with mock provider
    """
    if isinstance(response, str):
        responses = [response]
    else:
        responses = response

    provider = MockProvider(responses=responses)

    agent = Agent(
        runtime_id="test-agent",
        system_prompt="You are a test agent.",
        tools=["core"],
    )

    # Create fake runtime synchronously
    from yom.agent_runtime import CoreRuntime
    from yom.config import RuntimeSettings
    from yom.deps import RuntimeDeps

    settings = RuntimeSettings(
        runtime_id="test",
        system_prompt="You are a test agent.",
    )
    deps = RuntimeDeps()
    fake_runtime = CoreRuntime(deps=deps, settings=settings)
    fake_runtime._provider = provider

    # Override the runtime with our fake
    agent._runtime = fake_runtime

    return agent


# =============================================================================
# Response Assertions
# =============================================================================

def assert_response(
    response: str,
    *,
    contains: str | None = None,
    not_contains: str | None = None,
    matches: str | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    is_not_empty: bool = True,
) -> None:
    """Assert properties of a response.

    Args:
        response: The response to check
        contains: String that must be in response
        not_contains: String that must NOT be in response
        matches: Regex pattern that must match
        min_length: Minimum response length
        max_length: Maximum response length
        is_not_empty: Response must not be empty
    """
    import re

    assert isinstance(response, str), f"Response must be string, got {type(response)}"

    if is_not_empty:
        assert response.strip(), "Response is empty"

    if contains:
        assert contains in response, f"Response must contain '{contains}', got: {response[:100]}..."

    if not_contains:
        assert not_contains not in response, f"Response must not contain '{not_contains}', got: {response[:100]}..."

    if matches:
        assert re.search(matches, response), f"Response must match '{matches}', got: {response[:100]}..."

    if min_length is not None:
        assert len(response) >= min_length, f"Response too short (min={min_length}, got={len(response)})"

    if max_length is not None:
        assert len(response) <= max_length, f"Response too long (max={max_length}, got={len(response)})"


def assert_tool_calls(
    tool_calls: list[dict],
    *,
    names: list[str] | None = None,
    has_tool: str | None = None,
    count: int | None = None,
) -> None:
    """Assert properties of tool calls.

    Args:
        tool_calls: List of tool call dicts
        names: List of tool names that should be called
        has_tool: Tool name that should be in calls
        count: Expected number of tool calls
    """
    assert isinstance(tool_calls, list), f"Tool calls must be list, got {type(tool_calls)}"

    if count is not None:
        assert len(tool_calls) == count, f"Expected {count} tool calls, got {len(tool_calls)}"

    if has_tool:
        tool_names = [tc.get("name") for tc in tool_calls]
        assert has_tool in tool_names, f"Tool '{has_tool}' not found in {tool_names}"

    if names:
        tool_names = [tc.get("name") for tc in tool_calls]
        for name in names:
            assert name in tool_names, f"Tool '{name}' not found in {tool_names}"


# =============================================================================
# Test Fixtures
# =============================================================================

@dataclass
class AgentTestCase:
    """Test case for agent testing."""
    name: str
    prompt: str
    expected_contains: list[str] = field(default_factory=list)
    expected_tool_calls: list[str] = field(default_factory=list)
    max_turns: int = 10


@dataclass
class TestSuite:
    """Test suite for agent testing."""
    name: str
    cases: list[AgentTestCase]


async def run_test_suite(
    agent: Agent,
    suite: TestSuite,
    *,
    stop_on_first_failure: bool = True,
) -> dict[str, Any]:
    """Run a test suite against an agent.

    Args:
        agent: The agent to test
        suite: Test suite to run
        stop_on_first_failure: Stop on first failure

    Returns:
        Test results dict with passed/failed counts and details
    """
    results: dict[str, Any] = {
        "suite": suite.name,
        "passed": 0,
        "failed": 0,
        "tests": [],
    }


    for case in suite.cases:
        test_result: dict[str, Any] = {
            "name": case.name,
            "prompt": case.prompt,
            "passed": False,
            "response": "",
            "error": "",
        }

        try:
            response = await agent.run(case.prompt)
            test_result["response"] = response

            # Check expected content
            for expected in case.expected_contains:
                if expected not in response:
                    test_result["error"] = f"Missing expected content: '{expected}'"
                    break
            else:
                test_result["passed"] = True
                results["passed"] += 1

        except Exception as e:
            test_result["error"] = str(e)
            results["failed"] += 1

        results["tests"].append(test_result)

        if stop_on_first_failure and not test_result["passed"]:
            break

    return results


# =============================================================================
# Snapshot Testing
# =============================================================================

def snapshot_equal(a: dict, b: dict, ignore_keys: list[str] | None = None) -> bool:
    """Compare two snapshots, ignoring specified keys."""
    ignore_keys = ignore_keys or ["timestamp", "session_id"]

    def normalize(d):
        return {k: v for k, v in d.items() if k not in ignore_keys}

    return normalize(a) == normalize(b)


__all__ = [
    "MockProvider",
    "fake_agent",
    "assert_response",
    "assert_tool_calls",
    "AgentTestCase",
    "TestSuite",
    "run_test_suite",
    "snapshot_equal",
]
