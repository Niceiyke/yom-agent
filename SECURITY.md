# Security Policy

## Reporting

Please report vulnerabilities privately via repository security advisories.

## Scope

High priority:
- Tool execution sandbox bypasses
- Path traversal
- Command injection
- Secret leakage in logs/sessions

## Hardening

- Keep shell tool allowlist minimal.
- Avoid running destructive commands from agents.
- Use isolated runtime environments for untrusted prompts.
