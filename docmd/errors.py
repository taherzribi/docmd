"""Error taxonomy for docmd.

Kept flat and explicit (see ARCHITECTURE.md "Error handling") so callers -
CLI, library, and eventually the hosted API - can catch a small, well-known
set of exceptions instead of guessing at what a bare Exception means.
"""

from __future__ import annotations


class DocmdError(Exception):
    """Base class for all docmd errors."""


class UnsupportedFormatError(DocmdError):
    """Raised when the input file extension isn't handled by any converter."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        super().__init__(
            f"Unsupported file format: '{suffix}'. "
            "docmd currently supports: .pdf, .docx, .pptx "
            "(.docx/.pptx require `pip install docmd[full]`)."
        )


class MissingExtraError(DocmdError):
    """Raised when a format needs the `full` extra and it isn't installed."""

    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
        super().__init__(
            f"'{suffix}' files require the optional dependencies for "
            "DOCX/PPTX support. Install them with: pip install 'docmd[full]'"
        )


class MissingSystemDependencyError(DocmdError):
    """Raised when Marker's OCR/equation recognition needs a native binary
    that isn't installed - not a pip package, so `pip install docmd[full]`
    can't provide it. See ARCHITECTURE.md "OCR and equation recognition need
    a native binary" for why this exists."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            "OCR/equation recognition needs the `llama-server` binary from "
            "llama.cpp, which pip cannot install. This only matters for "
            "scanned PDFs or documents with equations - a normal text-layer "
            "PDF doesn't hit this path.\n\n"
            "Install it with:\n"
            "  macOS:  brew install llama.cpp\n"
            "  Linux:  brew install llama.cpp, or download a release from\n"
            "          https://github.com/ggml-org/llama.cpp/releases\n"
            "No Homebrew? Download the right archive from that releases "
            "page directly (llama-<version>-bin-macos-arm64.tar.gz etc.), "
            "then either put `llama-server` on your PATH or set "
            "LLAMA_CPP_BINARY to its full path.\n\n"
            f"Underlying error: {detail}"
        )


class EncryptedDocumentError(DocmdError):
    """Raised when the input is a password-protected / encrypted document."""

    def __init__(self) -> None:
        super().__init__(
            "This document is encrypted or password-protected. "
            "Remove the password before converting."
        )


class FileTooLargeError(DocmdError):
    """Raised when a file exceeds a caller-supplied hard size/page limit."""

    def __init__(self, limit_description: str) -> None:
        super().__init__(f"File too large: exceeds {limit_description}.")


class ConversionError(DocmdError):
    """Raised when the underlying conversion engine fails."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause
