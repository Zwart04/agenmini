#!/usr/bin/env bash
set -euo pipefail
family=$1
case "$family" in
  deb) apt-get update -qq; apt-get install -y /dist/agenmini_*_*.deb python3 ;;
  rpm) dnf install -y /dist/agenmini-*.rpm python3 shadow-utils ;;
  arch) pacman -Syu --noconfirm; pacman -U --noconfirm /dist/agenmini-*.pkg.tar.zst; pacman -S --needed --noconfirm python ;;
  *) exit 2 ;;
esac
useradd -m -s /bin/sh nativecheck
runuser -u nativecheck -- python3 /src/linux/check_installed.py
case "$family" in
  deb) apt-get remove -y agenmini ;;
  rpm) dnf remove -y agenmini ;;
  arch) pacman -R --noconfirm agenmini ;;
esac
test ! -e /opt/agenmini/launcher.py
echo "PASS native package install/run/remove: $family"
