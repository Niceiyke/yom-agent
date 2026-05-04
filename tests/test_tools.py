"""Tests for core tools."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from yom.tools.core import (
    read_file,
    write_file,
    edit_file,
    bash,
    cmd,
    _validate_path,
    CORE_TOOLS,
)


class TestPathValidation:
    """Tests for path validation security."""

    def test_validate_path_within_home(self):
        """Test that paths within home directory are allowed."""
        result = _validate_path("~/test.txt")
        assert isinstance(result, Path)

    def test_validate_path_escape_attempt(self):
        """Test that path traversal is blocked."""
        result = _validate_path("~/../../etc/passwd")
        assert isinstance(result, str)
        assert "escapes allowed directory" in result

    def test_validate_path_resolves_symlinks(self):
        """Test that paths with symlinks are resolved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "secret.txt"
            target.write_text("content")

            link = Path.home() / "external_link"
            try:
                link.symlink_to(target)
                result = _validate_path(str(link))
                # After resolving, link points outside ~ so should be blocked
                assert isinstance(result, str)
            finally:
                if link.exists():
                    link.unlink()


class TestReadFile:
    """Tests for read_file tool."""

    def test_read_file_returns_result_object(self):
        """Test that read_file returns a ToolResult object."""
        result = read_file("~/../../etc/passwd")
        assert hasattr(result, "content")
        assert hasattr(result, "tool_name")

    def test_read_file_escape_blocked(self):
        """Test that path traversal is blocked on read."""
        result = read_file("~/../../etc/passwd")
        assert "escapes allowed" in result.content or "Error" in result.content