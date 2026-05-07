"""Tiny helpers for opening files / folders in the user's file manager."""
import os
from pathlib import Path
from typing import Optional

from gi.repository import Gio, GLib


def open_path(path) -> bool:
    """Open a file or folder via the user's default handler."""
    if not path:
        return False
    p = str(path)
    if not os.path.exists(p):
        return False
    try:
        Gio.AppInfo.launch_default_for_uri(
            Path(p).resolve().as_uri(), None
        )
    except GLib.Error:
        return False
    return True


def folder_for_task_result(result) -> Optional[str]:
    """Pick a sensible folder to reveal for a finished task. ``result`` is
    the value returned by the music_backend command (a list of absolute
    paths when MPD is disabled)."""
    if not result:
        return None
    first = result[0]
    if not first:
        return None
    if os.path.isdir(first):
        return first
    parent = os.path.dirname(first)
    return parent if parent and os.path.isdir(parent) else None
