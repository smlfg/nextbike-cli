from __future__ import annotations

import errno
import json
import os
import pty
import re
import select
import stat
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "harness"
sys.path.insert(0, str(HARNESS))

from fake_server import FakeServer  # noqa: E402
from ux_spec import parse  # noqa: E402

SPEC = parse(ROOT / "docs" / "UX.md")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
TIMEOUT = 30.0


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    for relative in (".config", ".local/share", ".local/state", ".cache"):
        (home / relative).mkdir(parents=True, exist_ok=True)
    return home


def _env(server: FakeServer, home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "NEXTBIKE_BASE_URL": server.base_url,
            "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(HARNESS)]),
            "PYTHONUNBUFFERED": "1",
            "ACCEPTANCE_SANDBOX": "1",
            "ACCEPTANCE_NET_LOG": str(home / "net.log"),
            "TERM": "xterm",
            "LANG": "C.UTF-8",
        }
    )
    env.pop("PYTHONHOME", None)
    return env


def _run_tty(server: FakeServer, home: Path, *args: str) -> tuple[int, str]:
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, "-m", "nextbike", *args],
        cwd=str(ROOT),
        env=_env(server, home),
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
    )
    os.close(slave)
    chunks: list[bytes] = []
    deadline = time.monotonic() + TIMEOUT
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                raise AssertionError(f"nextbike {' '.join(args)} beendet sich nicht")
            ready, _, _ = select.select([master], [], [], remaining)
            if not ready:
                continue
            try:
                chunk = os.read(master, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(master)
    try:
        code = process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        code = process.wait()
    text = ANSI_RE.sub("", b"".join(chunks).decode("utf-8", "replace"))
    _assert_no_traceback(text)
    _assert_net_clean(home)
    return code, text


def _run_pipe(server: FakeServer, home: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, "-m", "nextbike", *args],
        cwd=str(ROOT),
        env=_env(server, home),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=TIMEOUT,
    )
    _assert_no_traceback(result.stdout + result.stderr)
    _assert_net_clean(home)
    return result


def _assert_no_traceback(text: str) -> None:
    assert "Traceback (most recent call last)" not in text


def _assert_net_clean(home: Path) -> None:
    log = home / "net.log"
    if log.exists():
        assert log.read_text(encoding="utf-8").strip() == ""


def test_staedte_finden(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        code, out = _run_tty(server, home, "staedte", "Mannheim")
        assert any("list_cities=1" in request.query for request in server.requests)
    assert code == 0, out
    assert "Städte zu „Mannheim“ (2 Treffer):" in out
    assert "Mannheim (UID 195, 112 Stationen)" in out
    assert "Roche - Mannheim (UID 860, 41 Stationen)" in out


def test_stationen_per_stichwort(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        code, out = _run_tty(server, home, "stationen", "Mannheim", "Lindenhof")
        assert any("city=195" in request.query for request in server.requests)
    assert code == 0, out
    expected = [
        "Stationen in Mannheim zu „Lindenhof“ (6 Treffer):",
        "25026 · Lindenhof - Jugendherberge · 3 ausleihbar, 3 Stellplätze frei",
        "25028 · Lindenhof - Johanniskirche · 1 ausleihbar, 2 Stellplätze frei",
        "25066 · Lindenhof - Meeräckerplatz · 15 ausleihbar, 0 Stellplätze frei",
        "25067 · Lindenhof - Hanns-Glückstein-Park · 14 ausleihbar, 0 Stellplätze frei",
        "25089 · Lindenhof / NTR · 0 ausleihbar, 0 Stellplätze frei",
        "25096 · Lindenhofplatz / HBF Süd · 0 ausleihbar, 0 Stellplätze frei",
    ]
    for line in expected:
        assert line in out


def test_station_im_detail(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        code, out = _run_tty(
            server,
            home,
            "station",
            "Lindenhof - Jugendherberge",
            "--stadt",
            "Mannheim",
        )
    assert code == 0, out
    expected = [
        "Lindenhof - Jugendherberge (Station 25026)",
        "Mannheim · 49.477082, 8.463662",
        "Räder: 3 (3 ausleihbar) · Stellplätze frei: 3 von 6",
        "Radtypen: 196 (3)",
        "Radnummern: 430037, 430852, 430059",
    ]
    for line in expected:
        assert line in out


def test_rad_per_nummer(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        code, out = _run_tty(server, home, "rad", "431211", "--stadt", "Mannheim")
    assert code == 0, out
    expected = [
        "Rad 431211 · Lindenhof - Meeräckerplatz (25066)",
        "Mannheim · Typ 179 · Zustand ok",
        "Akku: 100 % (ca. 60 km)",
    ]
    for line in expected:
        assert line in out


def test_stationen_in_der_naehe(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        code, out = _run_tty(
            server,
            home,
            "nah",
            "49.4771,8.4637",
            "--stadt",
            "Mannheim",
            "--radius",
            "1200",
        )
    assert code == 0, out
    expected = [
        "Stationen im Umkreis von 1200 m um 49.4771, 8.4637 (Mannheim):",
        "3 m · Lindenhof - Jugendherberge (25026) · 3 ausleihbar, 3 Stellplätze frei",
        "308 m · Lindenhofplatz / HBF Süd (25096) · 0 ausleihbar, 0 Stellplätze frei",
        "431 m · Lindenhof - Johanniskirche (25028) · 1 ausleihbar, 2 Stellplätze frei",
        "529 m · Lindenhof / NTR (25089) · 0 ausleihbar, 0 Stellplätze frei",
        "694 m · Lindenhof - Hanns-Glückstein-Park (25067) · 14 ausleihbar, 0 Stellplätze frei",
        "1021 m · Lindenhof - Meeräckerplatz (25066) · 15 ausleihbar, 0 Stellplätze frei",
    ]
    positions = [out.index(line) for line in expected]
    assert positions == sorted(positions), out


def test_watch_zweiter_aufruf(tmp_path: Path) -> None:
    home = _home(tmp_path)
    args = ("watch", "Lindenhof - Jugendherberge", "--stadt", "Mannheim")
    with FakeServer(SPEC, ROOT) as server:
        first_code, first_out = _run_tty(server, home, *args)
        second_code, second_out = _run_tty(server, home, *args)
    assert first_code == 0, first_out
    assert "Lindenhof - Jugendherberge (25026): 3 Räder verfügbar" in first_out
    assert "Erster Aufruf – Stand gespeichert." in first_out
    assert second_code == 0, second_out
    assert "Lindenhof - Jugendherberge (25026): 3 Räder verfügbar" in second_out
    assert "Unverändert seit letztem Aufruf." in second_out
    state_dir = home / ".local" / "state" / "nextbike-cli"
    state_files = [path for path in state_dir.glob("*") if path.is_file()]
    assert state_files
    for path in state_files:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_json_bei_pipe(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        result = _run_pipe(server, home, "staedte", "Mannheim")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["staedte"][0]["uid"] == 195
    assert data["staedte"][0]["name"] == "Mannheim"
