#!/usr/bin/env bash
# Serve an HTML report via a local HTTP server and open it in the browser.
#
# Usage: serve_report.sh /absolute/path/to/report.html [/serve/root/dir]
#
# - Kills any previous video-lens server via PID file
# - Starts serve_idle.py in the file's directory (or explicit root); it serves
#   like python3 http.server and exits by itself after 30 idle minutes
# - Opens the report in the default browser

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: serve_report.sh /path/to/report.html" >&2
    exit 1
fi

HTML_PATH="$1"

if [ ! -f "$HTML_PATH" ]; then
    echo "ERROR:SERVE_FILE_NOT_FOUND $HTML_PATH" >&2
    exit 1
fi

BYTES=$(wc -c < "$HTML_PATH" | tr -d ' ')
if [ "$BYTES" -lt 4096 ] || ! grep -q '</html>' "$HTML_PATH"; then
    echo "ERROR:SERVE_REPORT_INCOMPLETE size=$BYTES path=$HTML_PATH" >&2
    exit 1
fi

DIR="$(cd "$(dirname "$HTML_PATH")" && pwd)"
FILE="$(basename "$HTML_PATH")"
PORT=8765
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Command-line patterns of servers this script may replace: the current
# serve_idle.py, and the plain http.server that older versions started.
SERVER_PATTERN='serve_idle\.py|http\.server'

# Use explicit root if provided (tilde-expanded by caller), else fall back to heuristic
if [ $# -ge 2 ]; then
  SERVE_DIR="$(cd "$2" && pwd)"
  URL_PATH="${HTML_PATH#${SERVE_DIR}/}"
elif [[ "$(basename "$DIR")" == "reports" ]]; then
  SERVE_DIR="$(dirname "$DIR")"
  URL_PATH="reports/$FILE"
else
  SERVE_DIR="$DIR"
  URL_PATH="$FILE"
fi

PID_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/video-lens"
PID_FILE="$PID_DIR/server.pid"
SERVER_LOG="$PID_DIR/server.log"
mkdir -p "$PID_DIR"
if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    # Verify it's actually our http.server on this port before killing — match
    # against the full command line, not just the truncated comm name.
    if ps -p "$OLD_PID" -o args= 2>/dev/null | grep -Eq "($SERVER_PATTERN).*$PORT"; then
      kill "$OLD_PID" 2>/dev/null || true
      sleep 0.2
    fi
  fi
  rm -f "$PID_FILE"
fi

# The PID file only tracks servers started with the same cache dir. If the port
# is still occupied (stale server from another session or cache root), take it
# over only when it is one of our servers serving OUR directory; otherwise
# refuse loudly instead of letting the bind fail with an opaque
# SERVE_PORT_FAILED. Matching $SERVE_DIR keeps the "reclaim a stale video-lens
# session" intent while never killing an unrelated http.server the user is
# running for another project on this port.
LISTEN_PID="$(lsof -ti tcp:$PORT -sTCP:LISTEN 2>/dev/null | head -1 || true)"
if [ -n "$LISTEN_PID" ]; then
  LISTEN_ARGS="$(ps -p "$LISTEN_PID" -o args= 2>/dev/null || true)"
  if printf '%s' "$LISTEN_ARGS" | grep -Eq "$SERVER_PATTERN" \
     && printf '%s' "$LISTEN_ARGS" | grep -qF "$SERVE_DIR"; then
    kill "$LISTEN_PID" 2>/dev/null || true
    # Wait (up to ~2s) for the port to actually be released before binding.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      lsof -ti tcp:$PORT -sTCP:LISTEN >/dev/null 2>&1 || break
      sleep 0.2
    done
  else
    echo "ERROR:SERVE_PORT_BUSY port $PORT is in use by: $(ps -p "$LISTEN_PID" -o args= 2>/dev/null || echo "pid $LISTEN_PID")" >&2
    exit 1
  fi
fi

# Start HTTP server in background and detach it from this shell so it survives
# after the skill command exits. Log stderr/stdout so failures can be diagnosed.
# It stops on its own after 30 minutes without a request (serve_idle.py).
nohup python3 "$SCRIPT_DIR/serve_idle.py" "$PORT" --bind 127.0.0.1 --directory "$SERVE_DIR" \
  --pid-file "$PID_FILE" >"$SERVER_LOG" 2>&1 < /dev/null &
SERVER_PID=$!
echo "$SERVER_PID" > "$PID_FILE"
sleep 1

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "ERROR:SERVE_PORT_FAILED HTTP server failed to start on port $PORT" >&2
  if [ -s "$SERVER_LOG" ]; then
    echo "Last server log:" >&2
    tail -10 "$SERVER_LOG" >&2 || true
  fi
  rm -f "$PID_FILE"
  exit 1
fi

# Open in browser
URL="http://localhost:${PORT}/${URL_PATH}"
if [[ "${NO_BROWSER:-}" != "1" ]]; then
  if command -v open &>/dev/null; then
      open "$URL"
  elif command -v xdg-open &>/dev/null; then
      xdg-open "$URL"
  else
      echo "Open $URL in your browser"
  fi
fi

echo "HTML_REPORT: $HTML_PATH"
