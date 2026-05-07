"""Resolve, create and load the GUI's configuration file.

The native GUI shares the same INI format as the existing CLI/server. On
first launch we create a default file in $XDG_CONFIG_HOME so users don't
have to deal with the template manually.
"""
import os
import shutil
from configparser import ConfigParser
from pathlib import Path

CONFIG_DIR_NAME = "deezer-downloader"
CONFIG_FILE_NAME = "deezer-downloader.ini"
TEMPLATE_FILE = (
    Path(__file__).resolve().parent.parent / "cli" / "deezer-downloader.ini.template"
)


def resolve_config_path() -> Path:
    """Return the absolute path to the config file (may not exist yet)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def write_default_config(target: Path) -> None:
    """Write a freshly customised default config to ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    parser = ConfigParser()
    parser.read(TEMPLATE_FILE)

    parser["download_dirs"]["base"] = str(Path.home() / "Music" / CONFIG_DIR_NAME)
    parser["youtubedl"]["command"] = shutil.which("yt-dlp") or "/usr/bin/yt-dlp"

    with target.open("w") as fh:
        parser.write(fh)


def ensure_config() -> Path:
    """Make sure a config file exists; create defaults if not."""
    path = resolve_config_path()
    if not path.exists():
        write_default_config(path)
    return path
