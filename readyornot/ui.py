"""Terminal output: ANSI colours and word wrapping."""
from __future__ import annotations

import os
import shutil
import sys
import textwrap

STYLES = {
    "info": "",
    "dim": "\033[2m",
    "title": "\033[1m",
    "good": "\033[32m",
    "warn": "\033[33m",
    "alert": "\033[1;33m",
    "danger": "\033[1;31m",
    "radio": "\033[36m",
}
RESET = "\033[0m"



def _enable_ansi() -> bool:
    """Windows consoles only understand ANSI codes once virtual terminal mode is on."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except (AttributeError, OSError):
        return False


_color = sys.stdout.isatty() and "NO_COLOR" not in os.environ and _enable_ansi()


def set_color(enabled: bool) -> None:
    global _color
    _color = enabled


def width() -> int:
    return min(shutil.get_terminal_size((90, 24)).columns, 100) - 1


def paint(text: str, style: str = "info") -> str:
    code = STYLES.get(style, "")
    return f"{code}{text}{RESET}" if _color and code else text


def out(text: str = "", style: str = "info") -> None:
    w = width()
    lines = []
    for line in text.split("\n"):
        indent = len(line) - len(line.lstrip(" "))
        lines.extend(textwrap.wrap(line, w, subsequent_indent=" " * (indent + 2 if indent else 0),
                                   drop_whitespace=True) or [""])
    print(paint("\n".join(lines), style))


def rule(style: str = "dim") -> None:
    print(paint("-" * width(), style))
