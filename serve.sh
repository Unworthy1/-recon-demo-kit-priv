#!/usr/bin/env bash
# Instant local preview — no Docker required. Serves web/ on :8080 (or $1).
set -e
PORT="${1:-8080}"
cd "$(dirname "$0")/web"
echo "OpenRecon Kit → http://localhost:$PORT"
exec python3 -m http.server "$PORT"
