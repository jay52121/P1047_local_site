#!/bin/bash
set -u
cd "$(dirname "$0")"

PORT=5173
SOURCE_DIR="$PWD"
SERVE_DIR="${HOME}/Library/Application Support/SISP/P1047_local_site"
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)

if [ -z "$LAN_IP" ]; then
  echo "未找到局域网地址"
  exit 1
fi

mkdir -p "$SERVE_DIR"
ditto "$SOURCE_DIR" "$SERVE_DIR"
launchctl kickstart -k "gui/$(id -u)/local.sisp.p1047-site"

sleep 0.5
open "http://${LAN_IP}:${PORT}/person/P-1047/longitudinal-function/"
echo "SISP 服务已启动：http://${LAN_IP}:${PORT}"
