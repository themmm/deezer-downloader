"""Linux desktop entry point: native GTK4 / libadwaita application."""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from deezer_downloader.gui.config_io import ensure_config

APP_ID = "me.androidloves.deezer-downloader"


class DeezerDownloaderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self._window = None
        self._config_path = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._config_path = ensure_config()

        from deezer_downloader.configuration import load_config
        load_config(str(self._config_path))

    def do_activate(self):
        if self._window is None:
            from deezer_downloader.gui.window import MainWindow
            self._window = MainWindow(self, self._config_path)
        self._window.present()


def main() -> int:
    app = DeezerDownloaderApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
