# Changelog

## 0.1.2 (2026-05-08)

### Added
- `Agent.from_config()` for canonical YAML-based agent construction.
- Minimal `yom.rpc` JSON-RPC 2.0 request/response/error helpers.
- `define_tool()` and `pydantic_to_schema()` exports for explicit tool schemas.
- Expanded plugin primitives: `ProviderPlugin`, `MiddlewarePlugin`, `ToolVersionRegistry`, and `HotReloader`.

### Fixed
- CLI syntax/indentation errors and broken template helpers.
- CLI `run --config` and `chat --config` now use `Agent.from_config()`.
- Non-streaming duplicate user message in agent state.
- Sync tool double-execution in loop parallel execution.
- Tool call counting and `max_tool_calls` enforcement in the agent loop.
- `ToolCall.to_dict()` no longer emits generated IDs unexpectedly.
- Async retry backoff blocking (`time.sleep` -> `await asyncio.sleep`).
- YAML tool loading preserving string tool names.
- Invalid exports in `yom.tools.__all__`.
- Tool wrappers now support positional calls as well as keyword calls.
- Run-context parameters (`ctx`, `context`, `run_context`) are excluded from tool schemas.
- Session backend handling for manually injected runtimes and parallel fake agents.
- Pydantic required-field detection for generated tool schemas.

### Changed
- Documentation updated to distinguish hooks, plugins, and experimental extensions.
- `yom.extensions` is now explicitly marked experimental.
- Sub-agent frontmatter parsing now uses `yaml.safe_load()`.
- Sub-agent load warnings now use logging instead of `print()`.
- Default model changed from `MiniMax-M2.7` to `gpt-4o-mini`.
- Core path validation hardened to use path ancestry checks.
- Shell tool command allowlist reduced.
- Offline examples now avoid requiring live provider credentials.
