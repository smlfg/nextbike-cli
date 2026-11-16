from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _xdg_dir(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable)
    return Path(value) if value else Path.home() / fallback


def config_path() -> Path:
    return _xdg_dir("XDG_CONFIG_HOME", ".config") / "nextbike-cli" / "config.json"


def cache_dir() -> Path:
    return _xdg_dir("XDG_CACHE_HOME", ".cache") / "nextbike-cli"


def state_path() -> Path:
    return _xdg_dir("XDG_STATE_HOME", ".local/state") / "nextbike-cli" / "watch.json"


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def read_json(path: Path) -> Any | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return None


def write_json_atomic(path: Path, data: Any) -> None:
    ensure_private_dir(path.parent)
    descriptor, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
