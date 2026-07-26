"""On-disk locations for real exports and derived cache state."""

from __future__ import annotations

import os
from pathlib import Path


def data_home() -> Path:
    """Return the XDG data directory for this tool.

    Honors ``$XDG_DATA_HOME`` when set; otherwise uses
    ``~/.local/share/everydollar-reader``.
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg).expanduser() / "everydollar-reader"
    return Path.home() / ".local" / "share" / "everydollar-reader"


def ensure_data_home() -> Path:
    """Create and return the data directory."""
    root = data_home()
    root.mkdir(parents=True, exist_ok=True)
    return root
