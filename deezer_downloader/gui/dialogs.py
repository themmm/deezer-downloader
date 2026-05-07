"""Modal dialogs for direct downloads (playlist URL, favorites)."""
import re
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

PLAYLIST_PLACEHOLDER = (
    "https://www.deezer.com/de/playlist/123456789  or  123456789"
)
FAVORITES_PLACEHOLDER = (
    "Profile URL or user id — leave blank to use your own account"
)


def _make_input_dialog(parent: Optional[Gtk.Window],
                       heading: str,
                       body: str,
                       placeholder: str,
                       confirm_label: str,
                       on_submit: Callable[[str], None]) -> None:
    dialog = Adw.MessageDialog(
        transient_for=parent,
        modal=True,
        heading=heading,
        body=body,
    )
    entry = Gtk.Entry(placeholder_text=placeholder, hexpand=True)
    entry.set_activates_default(True)
    dialog.set_extra_child(entry)

    dialog.add_response("cancel", "Cancel")
    dialog.add_response("ok", confirm_label)
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")

    def _on_response(_dialog, response: str) -> None:
        if response == "ok":
            on_submit(entry.get_text().strip())
        dialog.destroy()

    dialog.connect("response", _on_response)
    dialog.present()


def prompt_playlist(parent: Optional[Gtk.Window],
                    on_submit: Callable[[str], None]) -> None:
    _make_input_dialog(
        parent=parent,
        heading="Download Deezer playlist",
        body="Paste the URL of a public playlist or just its numeric ID.",
        placeholder=PLAYLIST_PLACEHOLDER,
        confirm_label="Download",
        on_submit=on_submit,
    )


def prompt_favorites(parent: Optional[Gtk.Window],
                     on_submit: Callable[[str], None]) -> None:
    _make_input_dialog(
        parent=parent,
        heading="Download favorite tracks",
        body=(
            "Paste a Deezer profile URL, a user id, or leave the field "
            "blank to download your own loved tracks."
        ),
        placeholder=FAVORITES_PLACEHOLDER,
        confirm_label="Download",
        on_submit=on_submit,
    )


def extract_first_number(text: str) -> Optional[str]:
    """Pull the first numeric run out of text. Returns None if not found."""
    match = re.search(r"\d+", text)
    return match.group(0) if match else None
