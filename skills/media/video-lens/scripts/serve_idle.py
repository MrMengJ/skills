#!/usr/bin/env python3
"""Static file server for video-lens reports that exits once nobody is using it.

Usage: python3 serve_idle.py PORT --directory DIR [--bind ADDR]
                                  [--idle-timeout SECONDS] [--pid-file PATH]

Same behaviour as `python3 -m http.server`, plus an idle timer: every request
resets it, and when no request has arrived for --idle-timeout seconds the
server shuts itself down. A report page that is already open keeps working
after that (the player and timestamps do not need the server); only reloading
it or opening another report needs the server again, and serve_report.sh
starts a fresh one.

--idle-timeout 0 disables the timer. The VIDEO_LENS_IDLE_TIMEOUT environment
variable overrides the flag.
"""
import argparse
import functools
import os
import pathlib
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_IDLE_TIMEOUT = 1800  # 30 minutes


class _Activity:
    """Time of the last request, and how many are still being served."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last = time.monotonic()
        self._active = 0

    def begin(self):
        with self._lock:
            self._active += 1
            self._last = time.monotonic()

    def end(self):
        with self._lock:
            self._active -= 1
            self._last = time.monotonic()

    def idle_seconds(self):
        """Seconds since the last request finished; 0 while one is in flight."""
        with self._lock:
            if self._active > 0:
                return 0.0
            return time.monotonic() - self._last


class _Handler(SimpleHTTPRequestHandler):
    activity = None  # set per server in main()

    def handle_one_request(self):
        self.activity.begin()
        try:
            super().handle_one_request()
        finally:
            self.activity.end()


def _watch(httpd, activity, idle_timeout):
    poll = min(30.0, max(0.2, idle_timeout / 4))
    while activity.idle_seconds() < idle_timeout:
        time.sleep(poll)
    print(f"No requests for {idle_timeout}s; shutting down.", flush=True)
    httpd.shutdown()


def _remove_own_pid_file(pid_file):
    try:
        path = pathlib.Path(pid_file)
        if path.read_text().strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=int)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--idle-timeout", type=float, default=DEFAULT_IDLE_TIMEOUT)
    parser.add_argument("--pid-file")
    args = parser.parse_args()

    idle_timeout = args.idle_timeout
    env_timeout = os.environ.get("VIDEO_LENS_IDLE_TIMEOUT")
    if env_timeout:
        idle_timeout = float(env_timeout)

    activity = _Activity()
    handler = functools.partial(_Handler, directory=args.directory)
    _Handler.activity = activity

    httpd = ThreadingHTTPServer((args.bind, args.port), handler)
    httpd.daemon_threads = True
    if idle_timeout > 0:
        threading.Thread(target=_watch, args=(httpd, activity, idle_timeout), daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if args.pid_file:
            _remove_own_pid_file(args.pid_file)


if __name__ == "__main__":
    main()
