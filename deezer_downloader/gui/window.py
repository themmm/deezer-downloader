"""Main application window (libadwaita)."""
import re
import threading
from configparser import ConfigParser
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from deezer_downloader.gui.files import open_path
from deezer_downloader.gui.preferences import PreferencesDialog
from deezer_downloader.gui.queue import FINAL_STATES, QueuePage
from deezer_downloader.gui.result_item import SearchResult
from deezer_downloader.gui.search import SearchPage

DEFAULT_WIDTH = 1100
DEFAULT_HEIGHT = 780


def _spawn_preload(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def _extract_first_number(text: str):
    match = re.search(r"\d+", text)
    return match.group(0) if match else None


def _read_window_size(config_path: Path) -> tuple[int, int]:
    parser = ConfigParser()
    parser.read(config_path)
    try:
        w = parser.getint("gui", "width", fallback=DEFAULT_WIDTH)
        h = parser.getint("gui", "height", fallback=DEFAULT_HEIGHT)
    except (ValueError, KeyError):
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    return max(640, w), max(480, h)


def _write_window_size(config_path: Path, width: int, height: int) -> None:
    parser = ConfigParser()
    parser.read(config_path)
    if "gui" not in parser:
        parser["gui"] = {}
    parser["gui"]["width"] = str(width)
    parser["gui"]["height"] = str(height)
    try:
        with config_path.open("w") as fh:
            parser.write(fh)
    except OSError:
        pass


class MainWindow(Adw.ApplicationWindow):
    """Top-level window with search and queue views."""

    def __init__(self,
                 application: Adw.Application,
                 config_path: Path,
                 arl_missing: bool):
        width, height = _read_window_size(config_path)
        super().__init__(application=application,
                         default_width=width,
                         default_height=height,
                         title="Deezer Downloader")

        self._config_path = config_path
        self._force_quit = False
        self._toast_overlay = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()

        self.connect("close-request", self._on_close_request)

        if arl_missing:
            toolbar.add_top_bar(self._build_minimal_header())
            toolbar.set_content(self._build_arl_warning(config_path))
            self._toast_overlay.set_child(toolbar)
            self.set_content(self._toast_overlay)
            return

        self._search = SearchPage(
            on_enqueue=self._enqueue_download,
            on_playlist=self._enqueue_playlist,
            on_favorites=self._enqueue_favorites,
        )

        view_stack = Adw.ViewStack()
        view_stack.add_titled_with_icon(
            self._search, "search", "Search", "system-search-symbolic"
        )
        view_stack.add_titled_with_icon(
            QueuePage(
                on_toast=self._toast,
                on_completed=self._on_task_completed,
                on_retry=self._on_task_retry,
            ),
            "queue",
            "Queue",
            "folder-download-symbolic",
        )

        header = Adw.HeaderBar()
        switcher = Adw.ViewSwitcher(
            stack=view_stack,
            policy=Adw.ViewSwitcherPolicy.WIDE,
        )
        header.set_title_widget(switcher)
        header.pack_end(self._build_primary_menu_button())
        toolbar.add_top_bar(header)
        toolbar.set_content(view_stack)
        self._toast_overlay.set_child(toolbar)
        self.set_content(self._toast_overlay)

    # --- Sub-views ---------------------------------------------------------

    def _build_minimal_header(self) -> Adw.HeaderBar:
        header = Adw.HeaderBar()
        header.pack_end(self._build_primary_menu_button())
        return header

    def _build_primary_menu_button(self) -> Gtk.MenuButton:
        menu = Gio.Menu()
        menu.append("Open downloads folder", "app.open_downloads")
        menu.append("Preferences", "app.preferences")
        button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            tooltip_text="Main menu",
            menu_model=menu,
            primary=True,
        )
        return button

    def _build_arl_warning(self, config_path: Path) -> Gtk.Widget:
        page = Adw.StatusPage(
            icon_name="dialog-warning-symbolic",
            title="Deezer cookie missing",
            description=(
                "Open Preferences and paste your ARL cookie under "
                "Deezer → Account, then restart the app."
            ),
        )
        button = Gtk.Button(
            label="Open Preferences",
            css_classes=["suggested-action", "pill"],
            halign=Gtk.Align.CENTER,
        )
        button.connect("clicked", lambda _b: self.open_preferences())
        page.set_child(button)
        return page

    # --- Window lifecycle -------------------------------------------------

    def _on_close_request(self, _window) -> bool:
        # Persist window size first; even if the user cancels later, the
        # current size is still what they had on screen.
        w = self.get_width()
        h = self.get_height()
        if w > 0 and h > 0:
            _write_window_size(self._config_path, w, h)

        if self._force_quit:
            return False
        unfinished = self._unfinished_count()
        if unfinished == 0:
            return False

        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Quit while downloads are running?",
            body=(
                f"There {'is' if unfinished == 1 else 'are'} "
                f"{unfinished} download"
                f"{'s' if unfinished != 1 else ''} still pending or "
                "active. They will be cancelled if you quit now."
            ),
        )
        dialog.add_response("cancel", "Stay")
        dialog.add_response("quit", "Quit anyway")
        dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_quit_response)
        dialog.present()
        return True  # block; the dialog handler will re-fire close

    def _on_quit_response(self, _dialog, response: str) -> None:
        if response == "quit":
            self._force_quit = True
            self.close()

    def _unfinished_count(self) -> int:
        try:
            from deezer_downloader.web.music_backend import sched
        except ImportError:
            return 0
        return sum(
            1 for task in sched.all_tasks if task.state not in FINAL_STATES
        )

    # --- Preferences -------------------------------------------------------

    def open_preferences(self) -> None:
        dialog = PreferencesDialog(self, self._config_path)
        dialog.present()

    def open_downloads_folder(self) -> None:
        from deezer_downloader.configuration import config
        try:
            base = config["download_dirs"]["base"]
        except (KeyError, TypeError):
            self._toast("Download folder not configured")
            return
        if not open_path(base):
            self._toast(f"Could not open {base}")

    # --- Direct downloads --------------------------------------------------

    def _enqueue_playlist(self, raw: str) -> None:
        if not raw:
            self._toast("Please enter a playlist URL or ID")
            return
        if _extract_first_number(raw) is None:
            self._toast("Could not find a playlist ID in the input")
            return
        if self._is_duplicate(
            "download_deezer_playlist_and_queue_and_zip",
            playlist_id=raw,
        ):
            self._toast("Already in queue")
            return
        from deezer_downloader.web.music_backend import (
            preload_deezer_playlist,
            sched,
        )
        try:
            task = sched.add_pending(
                f"Playlist: {raw}",
                "download_deezer_playlist_and_queue_and_zip",
                playlist_id=raw,
                add_to_playlist=False,
                create_zip=False,
            )
        except Exception as exc:
            self._toast(f"Could not queue: {exc}")
            return
        _spawn_preload(preload_deezer_playlist, task, raw)
        self._toast("Added playlist to queue")

    def _enqueue_favorites(self, raw: str) -> None:
        user_id = _extract_first_number(raw) if raw else None
        if user_id is None:
            from deezer_downloader.deezer import get_my_user_id
            user_id = get_my_user_id()
        if not user_id:
            self._toast("Could not determine your Deezer user id")
            return
        if self._is_duplicate(
            "download_deezer_favorites",
            user_id=user_id,
        ):
            self._toast("Already in queue")
            return
        from deezer_downloader.web.music_backend import (
            preload_deezer_favorites,
            sched,
        )
        try:
            task = sched.add_pending(
                f"Favorites of user {user_id}",
                "download_deezer_favorites",
                user_id=user_id,
                add_to_playlist=False,
                create_zip=False,
            )
        except Exception as exc:
            self._toast(f"Could not queue: {exc}")
            return
        _spawn_preload(preload_deezer_favorites, task, user_id)
        self._toast(f"Added favorites of user {user_id} to queue")

    # --- Enqueue from search ----------------------------------------------

    def _enqueue_download(self, item: SearchResult) -> None:
        from deezer_downloader.web.music_backend import (
            preload_deezer_album,
            sched,
        )

        try:
            if item.id_type == "track":
                if self._is_duplicate(
                    "download_deezer_song_and_queue",
                    track_id=int(item.id),
                ):
                    self._toast("Already in queue")
                    return
                sched.add_pending(
                    f"Track: {item.artist} – {item.title}",
                    "download_deezer_song_and_queue",
                    track_id=int(item.id),
                    add_to_playlist=False,
                )
                msg = f"Added to queue: {item.title}"
            elif item.id_type == "album":
                if self._is_duplicate(
                    "download_deezer_album_and_queue_and_zip",
                    album_id=int(item.id),
                ):
                    self._toast("Already in queue")
                    return
                task = sched.add_pending(
                    f"Album: {item.artist} – {item.album}",
                    "download_deezer_album_and_queue_and_zip",
                    album_id=int(item.id),
                    add_to_playlist=False,
                    create_zip=False,
                )
                _spawn_preload(preload_deezer_album, task, int(item.id))
                msg = f"Added to queue: {item.album}"
            else:
                return
        except Exception as exc:
            self._toast(f"Could not queue: {exc}")
            return
        self._toast(msg)

    # --- Duplicate detection ----------------------------------------------

    def _is_duplicate(self, fn_name: str, **identity) -> bool:
        """True if there's already a non-final task with the same fn_name
        and the given identity kwargs (e.g. track_id or album_id)."""
        try:
            from deezer_downloader.web.music_backend import sched
        except ImportError:
            return False
        for task in sched.all_tasks:
            if task.fn_name != fn_name:
                continue
            if task.state in FINAL_STATES:
                continue
            if all(task.kwargs.get(k) == v for k, v in identity.items()):
                return True
        return False

    # --- Queue callbacks --------------------------------------------------

    def _on_task_completed(self, task) -> None:
        app = self.get_application()
        if app is None:
            return
        title = task.description or task.fn_name
        notification = Gio.Notification.new("Download complete")
        body = title
        subs = task.subtasks or []
        if subs:
            done = sum(1 for s in subs if s["state"] == "done")
            failed = sum(1 for s in subs if s["state"] == "failed")
            tail = f" ({done}/{len(subs)} tracks"
            if failed:
                tail += f", {failed} failed"
            tail += ")"
            body = f"{title}{tail}"
        notification.set_body(body)
        app.send_notification(f"deezer-downloader-{id(task)}", notification)

    def _on_task_retry(self, task) -> None:
        kwargs = dict(task.kwargs)
        fn_name = task.fn_name
        if self._is_duplicate(fn_name, **{
            k: kwargs[k] for k in ("track_id", "album_id", "playlist_id", "user_id")
            if k in kwargs
        }):
            self._toast("A retry is already in the queue")
            return

        from deezer_downloader.web.music_backend import (
            preload_deezer_album,
            preload_deezer_favorites,
            preload_deezer_playlist,
            sched,
        )

        try:
            new_task = sched.add_pending(task.description, fn_name, **kwargs)
        except Exception as exc:
            self._toast(f"Could not retry: {exc}")
            return

        if fn_name == "download_deezer_album_and_queue_and_zip":
            _spawn_preload(preload_deezer_album, new_task, kwargs["album_id"])
        elif fn_name == "download_deezer_playlist_and_queue_and_zip":
            _spawn_preload(preload_deezer_playlist, new_task, kwargs["playlist_id"])
        elif fn_name == "download_deezer_favorites":
            _spawn_preload(preload_deezer_favorites, new_task, kwargs["user_id"])

        self._toast("Retry added to queue – press Start to run it")

    def _toast(self, message: str) -> None:
        self._toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))
