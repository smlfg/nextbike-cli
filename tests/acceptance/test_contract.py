from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "tests" / "harness"
sys.path.insert(0, str(HARNESS))

from fake_server import FakeServer  # noqa: E402
from ux_spec import parse  # noqa: E402

SPEC = parse(ROOT / "docs" / "UX.md")


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    for relative in (".config", ".local/state", ".cache"):
        (home / relative).mkdir(parents=True, exist_ok=True)
    return home


def _env(home: Path, base_url: str = "http://127.0.0.1:1") -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_STATE_HOME": str(home / ".local" / "state"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "NEXTBIKE_BASE_URL": base_url,
            "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(HARNESS)]),
            "PYTHONUNBUFFERED": "1",
            "ACCEPTANCE_SANDBOX": "1",
            "ACCEPTANCE_NET_LOG": str(home / "net.log"),
            "LANG": "C.UTF-8",
        }
    )
    env.pop("PYTHONHOME", None)
    return env


def _run(home: Path, *args: str, base_url: str = "http://127.0.0.1:1"):
    return subprocess.run(
        [sys.executable, "-m", "nextbike", *args],
        cwd=str(ROOT),
        env=_env(home, base_url),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )


def _json(result: subprocess.CompletedProcess) -> dict:
    return json.loads(result.stdout)


def _assert_clean(result: subprocess.CompletedProcess) -> None:
    combined = result.stdout + result.stderr
    assert "Traceback (most recent call last)" not in combined


def test_help_und_version_mit_exit_0(tmp_path: Path) -> None:
    home = _home(tmp_path)
    for args in (("--help",), ("--version",), ("staedte", "--help")):
        result = _run(home, *args)
        assert result.returncode == 0, result.stderr
        _assert_clean(result)
    assert "nextbike" in _run(home, "--version").stdout


def test_unbekannter_befehl_als_json_mit_exit_2(tmp_path: Path) -> None:
    result = _run(_home(tmp_path), "gibtsnicht")
    assert result.returncode == 2
    _assert_clean(result)
    data = _json(result)
    assert data["fehler"]["code"] == "USAGE"
    assert data["fehler"]["naechster_schritt"]


def test_ungueltige_koordinaten_mit_exit_2(tmp_path: Path) -> None:
    result = _run(_home(tmp_path), "nah", "999,8")
    assert result.returncode == 2
    _assert_clean(result)
    assert _json(result)["fehler"]["code"] == "USAGE"


def test_netzfehler_mit_exit_3_und_json(tmp_path: Path) -> None:
    result = _run(_home(tmp_path), "staedte")
    assert result.returncode == 3
    _assert_clean(result)
    assert _json(result)["fehler"]["code"] == "QUELLE_FEHLER"


def test_stadt_nicht_gefunden_mit_exit_1(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        result = _run(home, "stationen", "Atlantis", base_url=server.base_url)
    assert result.returncode == 1
    _assert_clean(result)
    data = _json(result)
    assert data["fehler"]["code"] == "STADT_NICHT_GEFUNDEN"
    assert "nextbike staedte" in data["fehler"]["naechster_schritt"]


def test_standardstadt_aus_config(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        saved = _run(home, "config", "stadt", "Mannheim", base_url=server.base_url)
        detail = _run(
            home,
            "station",
            "Lindenhof - Jugendherberge",
            base_url=server.base_url,
        )
    assert saved.returncode == 0, saved.stderr
    assert _json(saved)["standardstadt"]["uid"] == 195
    assert detail.returncode == 0, detail.stderr
    assert _json(detail)["station"]["nummer"] == 25026
    config = home / ".config" / "nextbike-cli" / "config.json"
    assert stat.S_IMODE(config.stat().st_mode) == 0o600


def test_station_nicht_gefunden_mit_exit_1(tmp_path: Path) -> None:
    home = _home(tmp_path)
    with FakeServer(SPEC, ROOT) as server:
        result = _run(
            home,
            "station",
            "Gibt es nicht",
            "--stadt",
            "Mannheim",
            base_url=server.base_url,
        )
    assert result.returncode == 1
    _assert_clean(result)
    assert _json(result)["fehler"]["code"] == "STATION_NICHT_GEFUNDEN"
