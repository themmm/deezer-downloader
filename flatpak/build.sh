#!/usr/bin/env bash
# Build deezer-downloader as a Flatpak and install it for the current user.
#
# Run from the repo root or from inside flatpak/. The build output goes to
# ./build-flatpak/ (gitignored); flatpak-builder's cache lives in
# ./.flatpak-builder/.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

flatpak-builder --user --install --force-clean \
    build-flatpak flatpak/me.androidloves.deezer-downloader.yml

echo
echo "Installed. Launch with:"
echo "  flatpak run me.androidloves.deezer-downloader"
