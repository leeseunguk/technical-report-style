"""Typed failures for the DOCX style harness."""

from __future__ import annotations


class HarnessError(Exception):
    """Boundary error with a machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class ManuscriptError(HarnessError):
    """The JSON manuscript is malformed or fails an explicit reference check."""


class CollisionError(HarnessError):
    """The requested output would overwrite an input or an existing file."""


class PackageError(HarnessError):
    """The DOCX package cannot be reused without breaking the style contract."""
