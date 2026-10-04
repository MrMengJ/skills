"""The report server must stop by itself when idle, and not before."""
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SERVE_IDLE = Path(__file__).parent.parent / "scripts" / "serve_idle.py"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(tmp_path, idle_timeout, pid_file=None):
    (tmp_path / "report.html").write_text("<html>ok</html>")
    port = _free_port()
    cmd = [sys.executable, str(SERVE_IDLE), str(port), "--directory", str(tmp_path),
           "--idle-timeout", str(idle_timeout)]
    if pid_file:
        cmd += ["--pid-file", str(pid_file)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if pid_file:
        pid_file.write_text(str(proc.pid))
    url = f"http://127.0.0.1:{port}/report.html"
    for _ in range(50):  # wait for the socket to accept connections
        try:
            _get(url)
            break
        except OSError:
            time.sleep(0.1)
    return proc, url


def _get(url):
    with urllib.request.urlopen(url, timeout=2) as r:
        return r.status, r.read()


def test_serves_files_then_exits_when_idle(tmp_path):
    pid_file = tmp_path / "server.pid"
    proc, url = _start(tmp_path, idle_timeout=1, pid_file=pid_file)
    try:
        assert _get(url) == (200, b"<html>ok</html>")
        assert proc.wait(timeout=10) == 0
        assert not pid_file.exists(), "server should remove its own PID file on exit"
    finally:
        proc.kill()


def test_requests_keep_it_alive(tmp_path):
    proc, url = _start(tmp_path, idle_timeout=2)
    try:
        for _ in range(4):  # 4 s of activity, twice the idle timeout
            time.sleep(1)
            assert _get(url)[0] == 200
        assert proc.poll() is None, "server exited while still receiving requests"
        assert proc.wait(timeout=10) == 0
    finally:
        proc.kill()


def test_timeout_zero_never_exits(tmp_path):
    proc, url = _start(tmp_path, idle_timeout=0)
    try:
        time.sleep(1.5)
        assert proc.poll() is None
        assert _get(url)[0] == 200
    finally:
        proc.kill()
