"""Main application window (libadwaita)."""
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from deezer_downloader.gui.queue import QueuePage
from deezer_downloader.gui.result_item import SearchResult
from deezer_downloader.gui.search import SearchPage


class MainWindow(Adw.ApplicationWindow):
    """Top-level window with search and queue views."""

    def __init__(self,
                 application: Adw.Application,
                 config_path: Path,
                 arl_missing: bool):
        super().__init__(application=application,
                         default_width=1100,
                         default_height=780,
                         title="Deezer Downloader")

        self._toast_overlay = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()

        if arl_missing:
            toolbar.add_top_bar(Adw.HeaderBar())
            toolbar.set_content(self._build_arl_warning(config_path))
            self._toast_overlay.set_child(toolbar)
            self.set_content(self._toast_overlay)
            return

        self._search = SearchPage(on_enqueue=self._enqueue_download)

        view_stack = Adw.ViewStack()
        view_stack.add_titled_with_icon(
            self._search, "search", "Search", "system-search-symbolic"
        )
        view_stack.add_titled_with_icon(
            QueuePage(), "queue", "Queue",
            "folder-download-symbolic"
        )

        header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher(
            stack=view_stack,
            policy=Adw.ViewSwitcherPolicy.WIDE,
        )
        header.set_title_widget(switcher)
        toolbar.add_top_bar(header)
        toolbar.set_content(view_stack)
        self._toast_overlay.set_child(toolbar)
        self.set_content(self._toast_overlay)

    # --- Sub-views ---------------------------------------------------------

    def _build_arl_warning(self, config_path: Path) -> Gtk.Widget:
        return Adw.StatusPage(
            icon_name="dialog-warning-symbolic",
            title="Deezer cookie missing",
            description=(
                "Edit the config file and set cookie_arl under [deezer], "
                "then restart the app.\n\n"
                f"{config_path}"
            ),
        )

    # --- Enqueue -----------------------------------------------------------

    def _enqueue_download(self, item: SearchResult) -> None:
        from deezer_downloader.web.music_backend import sched

        try:
            if item.id_type == "track":
                sched.enqueue_task(
                    f"Track: {item.artist} – {item.title}",
                    "download_deezer_song_and_queue",
                    track_id=int(item.id),
                    add_to_playlist=False,
                )
                msg = f"Queued: {item.title}"
            elif item.id_type == "album":
                sched.enqueue_task(
                    f"Album: {item.artist} – {item.album}",
                    "download_deezer_album_and_queue_and_zip",
                    album_id=int(item.id),
                    add_to_playlist=False,
                    create_zip=False,
                )
                msg = f"Queued: {item.album}"
            else:
                return
        except Exception as exc:
            self._toast(f"Could not queue: {exc}")
            return
        self._toast(msg)

    def _toast(self, message: str) -> None:
        self._toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))
