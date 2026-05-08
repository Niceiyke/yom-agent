# Changelog

## 0.1.2 (unreleased)

### Fixed
- CLI syntax/indentation errors and broken template helpers.
- Non-streaming duplicate user message in agent state.
- Sync tool double-execution in loop parallel execution.
- Tool call counting in agent loop.
- Async retry backoff blocking (`time.sleep` -> `await asyncio.sleep`).
- YAML tool loading preserving string tool names.
- Invalid exports in `yom.tools.__all__`.

### Changed
- Documentation updated to remove unsupported APIs.
- Core path validation hardened to use path ancestry checks.
- Shell tool command allowlist reduced.
