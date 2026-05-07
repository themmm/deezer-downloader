"""Main application window (libadwaita)."""
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402


class MainWindow(Adw.ApplicationWindow):
    """Top-level window. Slice 1: header + placeholder content."""

    def __init__(self, application: Adw.Application, config_path: Path):
        super().__init__(application=application,
                         default_width=1100,
                         default_height=780,
                         title="Deezer Downloader")

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        status = Adw.StatusPage(
            icon_name="folder-music-symbolic",
            title="Deezer Downloader",
            description=(
                "Search and queue come in the next slice.\n"
                f"Config: {config_path}"
            ),
        )
        toolbar.set_content(status)

        self.set_content(toolbar)
