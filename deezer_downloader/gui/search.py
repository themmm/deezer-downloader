"""Search page: Deezer search bar + results list with download buttons."""
import threading
from typing import Callable

import requests
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from deezer_downloader.gui.result_item import SearchResult

SEARCH_TYPES = [
    ("track", "Tracks"),
    ("album", "Albums"),
    ("artist", "Artists"),
]


class SearchPage(Gtk.Box):
    """Search bar, type filter and result list."""

    def __init__(self, on_enqueue: Callable[[SearchResult], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_enqueue = on_enqueue
        self._store = Gio.ListStore.new(SearchResult)

        self.append(self._build_search_bar())
        self.append(self._build_results_view())

    # --- UI construction ---------------------------------------------------

    def _build_search_bar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                      margin_top=12, margin_bottom=6,
                      margin_start=12, margin_end=12)

        self._entry = Gtk.SearchEntry(hexpand=True,
                                      placeholder_text="Search Deezer…")
        self._entry.connect("activate", self._on_search_clicked)
        bar.append(self._entry)

        # Type filter
        self._type_buttons: dict[str, Gtk.ToggleButton] = {}
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                           css_classes=["linked"])
        first = None
        for value, label in SEARCH_TYPES:
            btn = Gtk.ToggleButton(label=label)
            if first is None:
                first = btn
                btn.set_active(True)
            else:
                btn.set_group(first)
            self._type_buttons[value] = btn
            type_box.append(btn)
        bar.append(type_box)

        search_btn = Gtk.Button(label="Search",
                                css_classes=["suggested-action"])
        search_btn.connect("clicked", self._on_search_clicked)
        bar.append(search_btn)

        return bar

    def _build_results_view(self) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow(vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)

        self._status = Adw.StatusPage(
            icon_name="system-search-symbolic",
            title="No search yet",
            description="Type a query above and press Enter.",
        )
        self._results_list = Gtk.ListBox(
            css_classes=["boxed-list"],
            selection_mode=Gtk.SelectionMode.NONE,
            margin_top=6, margin_bottom=12,
            margin_start=12, margin_end=12,
        )
        self._results_list.bind_model(self._store, self._make_row)

        self._content_stack = Gtk.Stack()
        self._content_stack.add_named(self._status, "empty")
        self._content_stack.add_named(self._results_list, "results")
        self._content_stack.set_visible_child_name("empty")

        scrolled.set_child(self._content_stack)
        return scrolled

    def _make_row(self, item: SearchResult) -> Gtk.Widget:
        row = Adw.ActionRow(title=GLib.markup_escape_text(item.primary_label()),
                            subtitle=GLib.markup_escape_text(item.secondary_label()))

        cover = Gtk.Image(icon_name="folder-music-symbolic",
                          pixel_size=48)
        row.add_prefix(cover)
        if item.img_url:
            self._load_cover_async(item.img_url, cover)

        if item.id_type in ("track", "album"):
            btn = Gtk.Button(icon_name="folder-download-symbolic",
                             tooltip_text="Add to download queue",
                             valign=Gtk.Align.CENTER)
            btn.connect("clicked", lambda _b: self._on_enqueue(item))
            row.add_suffix(btn)
        # Artists currently aren't enqueueable; a follow-up slice will add
        # "show top tracks" / "show albums" drilldowns.
        return row

    # --- Search ------------------------------------------------------------

    def _selected_type(self) -> str:
        for value, btn in self._type_buttons.items():
            if btn.get_active():
                return value
        return "track"

    def _on_search_clicked(self, _widget) -> None:
        query = self._entry.get_text().strip()
        if not query:
            return
        search_type = self._selected_type()
        self._show_loading(query)
        threading.Thread(
            target=self._do_search,
            args=(query, search_type),
            daemon=True,
        ).start()

    def _show_loading(self, query: str) -> None:
        self._status.set_icon_name("content-loading-symbolic")
        self._status.set_title("Searching…")
        self._status.set_description(f"“{query}”")
        self._content_stack.set_visible_child_name("empty")

    def _do_search(self, query: str, search_type: str) -> None:
        from deezer_downloader.deezer import deezer_search
        try:
            results = deezer_search(query, search_type)
        except Exception as exc:
            results = exc
        GLib.idle_add(self._apply_results, query, results)

    def _apply_results(self, query: str, results) -> bool:
        self._store.remove_all()
        if isinstance(results, Exception):
            self._status.set_icon_name("dialog-error-symbolic")
            self._status.set_title("Search failed")
            self._status.set_description(str(results))
            self._content_stack.set_visible_child_name("empty")
        elif not results:
            self._status.set_icon_name("system-search-symbolic")
            self._status.set_title("No results")
            self._status.set_description(f"Nothing found for “{query}”.")
            self._content_stack.set_visible_child_name("empty")
        else:
            for raw in results:
                self._store.append(SearchResult(raw))
            self._content_stack.set_visible_child_name("results")
        return False

    # --- Covers ------------------------------------------------------------

    def _load_cover_async(self, url: str, image: Gtk.Image) -> None:
        def fetch():
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                payload = resp.content
            except requests.RequestException:
                return
            GLib.idle_add(self._apply_cover, payload, image)

        threading.Thread(target=fetch, daemon=True).start()

    def _apply_cover(self, payload: bytes, image: Gtk.Image) -> bool:
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(payload)
            loader.close()
            pixbuf = loader.get_pixbuf()
        except GLib.Error:
            return False
        if pixbuf is not None:
            image.set_from_pixbuf(pixbuf)
        return False
