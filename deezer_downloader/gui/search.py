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
    """Search bar, type filter, result list and artist drilldown sub-pages."""

    def __init__(self, on_enqueue: Callable[[SearchResult], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_enqueue = on_enqueue
        self._store = Gio.ListStore.new(SearchResult)

        self._nav = Adw.NavigationView(vexpand=True, hexpand=True)
        main_page = Adw.NavigationPage(child=self._build_main_content(),
                                       title="Search")
        self._nav.add(main_page)
        self.append(self._nav)

    # --- Main page --------------------------------------------------------

    def _build_main_content(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self._build_search_bar())
        box.append(self._build_results_view())
        return box

    def _build_search_bar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                      margin_top=12, margin_bottom=6,
                      margin_start=12, margin_end=12)

        self._entry = Gtk.SearchEntry(hexpand=True,
                                      placeholder_text="Search Deezer…")
        self._entry.connect("activate", self._on_search_clicked)
        bar.append(self._entry)

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

    # --- Row factory (shared between main and sub-pages) ------------------

    def _make_row(self, item: SearchResult) -> Gtk.Widget:
        row = Adw.ActionRow(title=GLib.markup_escape_text(item.primary_label()),
                            subtitle=GLib.markup_escape_text(item.secondary_label()))

        cover = Gtk.Image(icon_name="folder-music-symbolic",
                          pixel_size=48)
        row.add_prefix(cover)
        if item.img_url:
            self._load_cover_async(item.img_url, cover)

        if item.id_type in ("track", "album"):
            dl_btn = Gtk.Button(icon_name="folder-download-symbolic",
                                tooltip_text="Add to download queue",
                                valign=Gtk.Align.CENTER)
            dl_btn.connect("clicked", lambda _b: self._on_enqueue(item))
            row.add_suffix(dl_btn)
        elif item.id_type == "artist":
            top_btn = Gtk.Button(icon_name="starred-symbolic",
                                 tooltip_text="Top tracks",
                                 valign=Gtk.Align.CENTER)
            top_btn.connect("clicked",
                            lambda _b: self._push_artist_view(item, "artist_top"))
            row.add_suffix(top_btn)

            albums_btn = Gtk.Button(icon_name="media-optical-symbolic",
                                    tooltip_text="Albums",
                                    valign=Gtk.Align.CENTER)
            albums_btn.connect("clicked",
                               lambda _b: self._push_artist_view(item, "artist_album"))
            row.add_suffix(albums_btn)
        return row

    # --- Search (main page) -----------------------------------------------

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

    # --- Artist drilldown -------------------------------------------------

    def _push_artist_view(self, artist: SearchResult, search_type: str) -> None:
        kind_label = "Top tracks" if search_type == "artist_top" else "Albums"
        page_title = f"{kind_label} – {artist.artist}"

        sub_store = Gio.ListStore.new(SearchResult)
        sub_listbox = Gtk.ListBox(
            css_classes=["boxed-list"],
            selection_mode=Gtk.SelectionMode.NONE,
            margin_top=12, margin_bottom=12,
            margin_start=12, margin_end=12,
        )
        sub_listbox.bind_model(sub_store, self._make_row)

        scroller = Gtk.ScrolledWindow(
            vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        scroller.set_child(sub_listbox)

        sub_status = Adw.StatusPage(
            icon_name="content-loading-symbolic",
            title="Loading…",
            description=f"Fetching {kind_label.lower()} for {artist.artist}",
        )

        sub_stack = Gtk.Stack()
        sub_stack.add_named(sub_status, "loading")
        sub_stack.add_named(scroller, "results")
        sub_stack.set_visible_child_name("loading")

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        toolbar.set_content(sub_stack)

        page = Adw.NavigationPage(child=toolbar, title=page_title)
        self._nav.push(page)

        threading.Thread(
            target=self._do_drilldown,
            args=(artist.id, search_type, sub_store, sub_stack,
                  sub_status, kind_label, artist.artist),
            daemon=True,
        ).start()

    def _do_drilldown(self, artist_id, search_type, store, stack, status,
                      kind_label, artist_name) -> None:
        from deezer_downloader.deezer import deezer_search
        try:
            results = deezer_search(artist_id, search_type)
        except Exception as exc:
            results = exc
        GLib.idle_add(self._apply_drilldown, results, store, stack, status,
                      kind_label, artist_name)

    def _apply_drilldown(self, results, store, stack, status,
                         kind_label, artist_name) -> bool:
        if isinstance(results, Exception):
            status.set_icon_name("dialog-error-symbolic")
            status.set_title("Failed to load")
            status.set_description(str(results))
        elif not results:
            status.set_icon_name("system-search-symbolic")
            status.set_title("Nothing here")
            status.set_description(
                f"No {kind_label.lower()} found for {artist_name}."
            )
        else:
            for raw in results:
                store.append(SearchResult(raw))
            stack.set_visible_child_name("results")
        return False

    # --- Covers -----------------------------------------------------------

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
