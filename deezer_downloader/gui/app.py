"""Linux desktop entry point: native GTK4 / libadwaita application."""
import sys
from configparser import ConfigParser
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from deezer_downloader.gui.config_io import ensure_config

APP_ID = "me.androidloves.deezer-downloader"
ARL_PLACEHOLDER = "[a-f0-9]{192}"


def _arl_is_unset(config_path: Path) -> bool:
    parser = ConfigParser()
    parser.read(config_path)
    arl = parser.get("deezer", "cookie_arl", fallback="").strip()
    return arl == "" or arl == ARL_PLACEHOLDER


class DeezerDownloaderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self._window = None
        self._config_path = None
        self._arl_missing = False
        self._workers_running = False

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._config_path = ensure_config()
        self._arl_missing = _arl_is_unset(self._config_path)

        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)
        self.set_accels_for_action("app.preferences", ["<Primary>comma"])

        open_dl_action = Gio.SimpleAction.new("open_downloads", None)
        open_dl_action.connect("activate", self._on_open_downloads)
        self.add_action(open_dl_action)

        if self._arl_missing:
            return

        from deezer_downloader.configuration import load_config
        load_config(str(self._config_path))

        from deezer_downloader.deezer import init_deezer_session
        from deezer_downloader.configuration import config
        init_deezer_session(config["proxy"]["server"],
                            config["deezer"]["quality"])

        from deezer_downloader.web.music_backend import sched
        sched.run_workers(config.getint("threadpool", "workers"))
        self._workers_running = True

        self.connect("shutdown", self._on_shutdown)

    def do_activate(self):
        if self._window is None:
            from deezer_downloader.gui.window import MainWindow
            self._window = MainWindow(self,
                                      self._config_path,
                                      self._arl_missing)
        self._window.present()

    def _on_preferences(self, _action, _param):
        if self._window is not None:
            self._window.open_preferences()

    def _on_open_downloads(self, _action, _param):
        if self._window is not None and not self._arl_missing:
            self._window.open_downloads_folder()

    def _on_shutdown(self, _app):
        if self._workers_running:
            from deezer_downloader.web.music_backend import sched
            sched.stop_workers_now()
            self._workers_running = False


def main() -> int:
    app = DeezerDownloaderApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
