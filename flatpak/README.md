# Flatpak build (local use)

Bundles deezer-downloader as a Flatpak so the GTK frontend runs in a
sandbox with its own GTK4 / libadwaita runtime — no system PyGObject
install or `--system-site-packages` venv required. Aimed at building
and using locally on your own machine; not set up for Flathub
submission.

## One-time setup

```bash
# Arch / CachyOS
sudo pacman -S flatpak flatpak-builder

# Debian / Ubuntu
sudo apt-get install flatpak flatpak-builder

# Fedora
sudo dnf install flatpak flatpak-builder
```

Add the Flathub remote (only for pulling the GNOME runtime; we don't
publish there) and install the GNOME 50 SDK:

```bash
flatpak remote-add --if-not-exists --user flathub \
    https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub \
    org.gnome.Platform//50 org.gnome.Sdk//50
```

## Build and install

From the repository root:

```bash
flatpak/build.sh
```

That's a thin wrapper around `flatpak-builder --user --install
--force-clean build-flatpak flatpak/me.androidloves.deezer-downloader.yml`.
Build artefacts go to `build-flatpak/` and the builder cache to
`.flatpak-builder/`; both are gitignored.

Launch the app:

```bash
flatpak run me.androidloves.deezer-downloader
```

It also shows up in your application menu as **Deezer Downloader**.

## Where files end up

| What           | Path                                                                         |
| -------------- | ---------------------------------------------------------------------------- |
| App config     | `~/.var/app/me.androidloves.deezer-downloader/config/deezer-downloader/`     |
| Window state   | same folder, `window-state.json`                                             |
| Downloads      | `~/Music/deezer-downloader/` (host filesystem)                               |

The `--filesystem=xdg-music` permission in the manifest gives the
sandbox write access to your real `~/Music/` directory, so files end up
on the host where you'd expect them.

## Caveats

- **ffmpeg is not bundled.** Pure Deezer downloads (MP3 / FLAC straight
  from the CDN) don't need it. yt-dlp audio extraction from YouTube
  does — add an `ffmpeg` module to the manifest if you want that.
- **MPD integration is disabled by design.** The sandbox can't reach
  `localhost:6600` to talk to the host's MPD daemon without extra
  permissions; keep `use_mpd = False` in the INI.

## Uninstall

```bash
flatpak uninstall --user me.androidloves.deezer-downloader
```

User data under `~/.var/app/me.androidloves.deezer-downloader/` stays
behind so your config survives reinstalls; remove it manually if you
want a clean slate.
