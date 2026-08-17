#!/bin/zsh
set -euo pipefail
ROOT=${0:A:h}
APP="$ROOT/dist/SISP Local Site.app"
DEV=/Applications/Xcode.app/Contents/Developer
cd "$ROOT"
DEVELOPER_DIR="$DEV" swift build -c release
BIN=$(DEVELOPER_DIR="$DEV" swift build -c release --show-bin-path)
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN/SISPLocalSite" "$APP/Contents/MacOS/"
cp "$ROOT/App/Info.plist" "$APP/Contents/Info.plist"
codesign --force --deep --sign - "$APP"
print "$APP"
