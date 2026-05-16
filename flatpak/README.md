# Flatpak build

This folder bundles deezer-downloader as a Flatpak so the GTK frontend
runs in a sandbox with its own GTK4 / libadwaita runtime — no system
PyGObject install or `--system-site-packages` venv required.

## Prerequisites

```bash
# Arch / CachyOS
sudo pacman -S flatpak flatpak-builder

# Debian / Ubuntu
sudo apt-get install flatpak flatpak-builder

# Fedora
sudo dnf install flatpak flatpak-builder
```

Add the Flathub remote (once per machine) and install the GNOME 47 SDK:

```bash
flatpak remote-add --if-not-exists --user flathub \
    https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub \
    org.gnome.Platform//47 org.gnome.Sdk//47
```

## Build and install

From the repository root:

```bash
flatpak-builder --user --install --force-clean \
    build-flatpak flatpak/me.androidloves.deezer-downloader.yml
```

This will:

1. Spin up an isolated build sandbox with the GNOME 47 SDK
2. `pip install` the Python runtime dependencies into `/app`
3. Install the project itself (including the `deezer-downloader-gui`
   script and the GUI package) into `/app`
4. Drop the `.desktop` entry, SVG icon and AppStream metainfo into the
   right `/app/share/...` locations
5. Install the finished bundle for your user

Launch it:

```bash
flatpak run me.androidloves.deezer-downloader
```

It also shows up in your application menu as **Deezer Downloader**.

## Where files end up

Inside the sandbox:

| What                       | Path inside sandbox                              |
| -------------------------- | ------------------------------------------------ |
| App config                 | `~/.var/app/me.androidloves.deezer-downloader/config/deezer-downloader/` |
| Window state               | same folder, `window-state.json`                 |
| Downloads                  | `~/Music/deezer-downloader/` (host filesystem)   |

The `--filesystem=xdg-music` permission in the manifest gives the
sandbox write access to your real `~/Music/` directory, so files end up
on the host where you'd expect them.

## Caveats

- **ffmpeg is not bundled.** Pure Deezer downloads (MP3 / FLAC straight
  from the CDN) don't need it. yt-dlp audio extraction from YouTube
  does — if you want that, add an `ffmpeg` module to the manifest or
  pull in the shared `org.freedesktop.Platform` ffmpeg module.
- **MPD integration is disabled by design.** The sandbox can't reach
  `localhost:6600` to talk to the host's MPD daemon without extra
  permissions; keep `use_mpd = False` in the INI.
- **The online pip install** in the manifest means the build is not
  reproducible. For Flathub-style hermetic builds, replace the
  `python-deps` module with output from
  [`flatpak-pip-generator`](https://github.com/flatpak/flatpak-builder-tools/tree/master/pip)
  that pins every wheel by sha256.

## Uninstall

```bash
flatpak uninstall --user me.androidloves.deezer-downloader
```

User data under `~/.var/app/me.androidloves.deezer-downloader/` stays
behind so your config survives reinstalls; remove it manually if you
want a clean slate.
