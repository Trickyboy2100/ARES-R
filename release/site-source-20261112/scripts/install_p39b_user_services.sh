#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/.." && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
cp "$repo_dir/deploy/systemd/ares-r-backend.service" "$unit_dir/ares-r-backend.service"
cp "$repo_dir/deploy/systemd/ares-r-webui.service" "$unit_dir/ares-r-webui.service"
systemctl --user daemon-reload
systemctl --user enable ares-r-backend.service ares-r-webui.service
systemctl --user restart ares-r-backend.service
for _ in $(seq 1 30); do
  curl --fail --silent http://127.0.0.1:8766/health >/dev/null && break
  sleep 1
done
curl --fail http://127.0.0.1:8766/health
systemctl --user restart ares-r-webui.service
systemctl --user is-enabled ares-r-backend.service ares-r-webui.service
systemctl --user is-active ares-r-backend.service ares-r-webui.service
