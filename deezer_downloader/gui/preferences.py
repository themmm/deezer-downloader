"""Preferences dialog backed by the deezer-downloader.ini file."""
from configparser import ConfigParser
from pathlib import Path
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

QUALITIES = ["mp3", "flac"]
ARL_PLACEHOLDER = "[a-f0-9]{192}"


def _read(config_path: Path) -> ConfigParser:
    parser = ConfigParser()
    parser.read(config_path)
    return parser


def _write(config_path: Path, parser: ConfigParser) -> None:
    with config_path.open("w") as fh:
        parser.write(fh)


class PreferencesDialog(Adw.PreferencesWindow):
    """Edit the INI file from the GUI. Most changes need an app restart."""

    def __init__(self,
                 parent: Optional[Gtk.Window],
                 config_path: Path,
                 on_changed: Optional[Callable[[], None]] = None):
        super().__init__(
            transient_for=parent,
            modal=True,
            title="Preferences",
        )
        self._config_path = config_path
        self._on_changed = on_changed
        self._parser = _read(config_path)
        self._suspend_signals = False

        self.add(self._build_deezer_page())
        self.add(self._build_downloads_page())
        self.add(self._build_advanced_page())

    # --- Pages -------------------------------------------------------------

    def _build_deezer_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(
            title="Deezer", icon_name="folder-music-symbolic"
        )
        group = Adw.PreferencesGroup(
            title="Account",
            description=(
                "Log in at deezer.com, open developer tools → Storage → "
                "Cookies, copy the value of the 'arl' cookie and paste it "
                "here."
            ),
        )

        arl = self._get("deezer", "cookie_arl")
        if arl == ARL_PLACEHOLDER:
            arl = ""
        self._arl_row = Adw.PasswordEntryRow(title="ARL cookie")
        self._arl_row.set_text(arl)
        self._arl_row.set_show_apply_button(True)
        self._arl_row.connect("apply", self._on_arl_apply)
        group.add(self._arl_row)

        self._quality_row = Adw.ComboRow(title="Quality")
        model = Gtk.StringList.new(QUALITIES)
        self._quality_row.set_model(model)
        current = self._get("deezer", "quality") or "mp3"
        if current in QUALITIES:
            self._quality_row.set_selected(QUALITIES.index(current))
        self._quality_row.connect("notify::selected", self._on_quality_changed)
        group.add(self._quality_row)

        page.add(group)
        return page

    def _build_downloads_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(
            title="Downloads", icon_name="folder-download-symbolic"
        )
        group = Adw.PreferencesGroup(
            title="Storage",
            description=(
                "Songs, albums, playlists and zips are stored under the "
                "base directory."
            ),
        )

        self._base_row = Adw.ActionRow(
            title="Base directory",
            subtitle=self._get("download_dirs", "base"),
        )
        pick = Gtk.Button(
            icon_name="folder-open-symbolic",
            tooltip_text="Choose folder",
            valign=Gtk.Align.CENTER,
        )
        pick.connect("clicked", self._pick_base_dir)
        self._base_row.add_suffix(pick)
        self._base_row.set_activatable_widget(pick)
        group.add(self._base_row)

        page.add(group)

        ytdl_group = Adw.PreferencesGroup(title="yt-dlp")
        self._ytdl_row = Adw.EntryRow(title="yt-dlp command")
        self._ytdl_row.set_text(self._get("youtubedl", "command"))
        self._ytdl_row.set_show_apply_button(True)
        self._ytdl_row.connect("apply", self._on_ytdl_apply)
        ytdl_group.add(self._ytdl_row)
        page.add(ytdl_group)

        return page

    def _build_advanced_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(
            title="Advanced", icon_name="emblem-system-symbolic"
        )
        group = Adw.PreferencesGroup(
            title="Proxy",
            description=(
                "Optional. Examples: https://user:pass@host:port or "
                "socks5://127.0.0.1:9050"
            ),
        )
        self._proxy_row = Adw.EntryRow(title="Proxy server")
        self._proxy_row.set_text(self._get("proxy", "server"))
        self._proxy_row.set_show_apply_button(True)
        self._proxy_row.connect("apply", self._on_proxy_apply)
        group.add(self._proxy_row)
        page.add(group)
        return page

    # --- Helpers -----------------------------------------------------------

    def _get(self, section: str, key: str) -> str:
        return self._parser.get(section, key, fallback="").strip()

    def _set_and_save(self, section: str, key: str, value: str) -> None:
        if section not in self._parser:
            self._parser[section] = {}
        self._parser[section][key] = value
        _write(self._config_path, self._parser)
        if self._on_changed is not None:
            self._on_changed()

    def _refresh_runtime_config(self) -> bool:
        """Pull the saved values into the running app's config. Returns True
        when the live config was actually refreshed."""
        from deezer_downloader.configuration import config as live
        if live is None:
            return False
        live.read(self._config_path)
        return True

    def _reinit_session(self) -> Optional[str]:
        """Re-initialise the Deezer session in place. Returns an error
        message on failure, None on success."""
        from deezer_downloader.configuration import config as live
        if live is None:
            return "not-initialised"
        try:
            from deezer_downloader.deezer import init_deezer_session
            init_deezer_session(live["proxy"]["server"],
                                live["deezer"]["quality"])
        except Exception as exc:
            return str(exc)
        return None

    def _toast_ok(self, message: str = "Updated") -> None:
        self.add_toast(Adw.Toast(title=message, timeout=2))

    def _toast_restart_hint(self) -> None:
        self.add_toast(
            Adw.Toast(title="Restart the app to apply changes", timeout=4)
        )

    def _toast_error(self, message: str) -> None:
        self.add_toast(Adw.Toast(title=message, timeout=5))

    def _apply_session_change(self, label: str) -> None:
        if not self._refresh_runtime_config():
            self._toast_restart_hint()
            return
        err = self._reinit_session()
        if err is None:
            self._toast_ok(f"{label} updated")
        elif err == "not-initialised":
            self._toast_restart_hint()
        else:
            self._toast_error(f"{label}: {err}")

    # --- Signal handlers ---------------------------------------------------

    def _on_arl_apply(self, entry: Adw.PasswordEntryRow) -> None:
        if self._suspend_signals:
            return
        self._set_and_save("deezer", "cookie_arl", entry.get_text().strip())
        self._apply_session_change("ARL")

    def _on_quality_changed(self, row: Adw.ComboRow, _pspec) -> None:
        if self._suspend_signals:
            return
        idx = row.get_selected()
        if 0 <= idx < len(QUALITIES):
            self._set_and_save("deezer", "quality", QUALITIES[idx])
            self._apply_session_change("Quality")

    def _on_ytdl_apply(self, entry: Adw.EntryRow) -> None:
        if self._suspend_signals:
            return
        self._set_and_save("youtubedl", "command", entry.get_text().strip())
        if self._refresh_runtime_config():
            self._toast_ok("yt-dlp path updated")

    def _on_proxy_apply(self, entry: Adw.EntryRow) -> None:
        if self._suspend_signals:
            return
        self._set_and_save("proxy", "server", entry.get_text().strip())
        self._apply_session_change("Proxy")

    def _pick_base_dir(self, _button) -> None:
        dialog = Gtk.FileDialog(title="Choose download folder")
        current = self._get("download_dirs", "base")
        if current and Path(current).exists():
            dialog.set_initial_folder(Gio.File.new_for_path(current))
        dialog.select_folder(self, None, self._pick_base_dir_done)

    def _pick_base_dir_done(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            gfile = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path:
            return
        self._set_and_save("download_dirs", "base", path)
        self._base_row.set_subtitle(path)
        if self._refresh_runtime_config():
            try:
                from deezer_downloader.web.music_backend import (
                    check_download_dirs_exist,
                )
                check_download_dirs_exist()
            except Exception as exc:
                self._toast_error(f"Could not create folders: {exc}")
                return
            self._toast_ok("Download folder updated")
        else:
            self._toast_restart_hint()
