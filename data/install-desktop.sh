#!/usr/bin/env bash
# Install the Deezer Downloader app icon and .desktop entry into the user's
# XDG data directory so it shows up in the application menu.
#
# Usage:   ./data/install-desktop.sh
# Removes: ./data/install-desktop.sh --uninstall
set -euo pipefail

APP_ID="me.androidloves.deezer-downloader"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"

DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"

DESKTOP_DEST="$DESKTOP_DIR/$APP_ID.desktop"
ICON_DEST="$ICON_DIR/$APP_ID.svg"

uninstall() {
  rm -f "$DESKTOP_DEST" "$ICON_DEST"
  echo "Removed $DESKTOP_DEST"
  echo "Removed $ICON_DEST"
}

install() {
  mkdir -p "$DESKTOP_DIR" "$ICON_DIR"
  install -m 0644 "$SCRIPT_DIR/applications/$APP_ID.desktop" "$DESKTOP_DEST"
  install -m 0644 "$SCRIPT_DIR/icons/$APP_ID.svg" "$ICON_DEST"
  echo "Installed $DESKTOP_DEST"
  echo "Installed $ICON_DEST"

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f "$DATA_HOME/icons/hicolor" || true
  fi
}

case "${1:-install}" in
  --uninstall|uninstall) uninstall ;;
  install|"") install ;;
  *) echo "Unknown argument: $1" >&2; exit 2 ;;
esac
