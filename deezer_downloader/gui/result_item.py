"""GObject wrapper for a single search result, usable in Gio.ListStore."""
from gi.repository import GObject


class SearchResult(GObject.Object):
    """A normalised search hit. Mirrors deezer.deezer_search output keys."""

    __gtype_name__ = "DDSearchResult"

    id = GObject.Property(type=str)
    id_type = GObject.Property(type=str)
    title = GObject.Property(type=str)
    artist = GObject.Property(type=str)
    album = GObject.Property(type=str)
    img_url = GObject.Property(type=str)

    def __init__(self, raw: dict):
        super().__init__()
        self.id = str(raw.get("id", ""))
        self.id_type = raw.get("id_type", "")
        self.title = raw.get("title", "")
        self.artist = raw.get("artist", "")
        self.album = raw.get("album", "")
        self.img_url = raw.get("img_url", "")

    def primary_label(self) -> str:
        if self.id_type == "track":
            return self.title or "(unknown title)"
        if self.id_type == "album":
            return self.album or "(unknown album)"
        return self.artist or "(unknown artist)"

    def secondary_label(self) -> str:
        if self.id_type == "track":
            return f"{self.artist} – {self.album}".strip(" –")
        if self.id_type == "album":
            return self.artist
        return ""
