"""
Persistent configuration: port, bearer token, cache size, confirmations.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any, Dict, Optional

_lock = threading.RLock()

_DEFAULTS: Dict[str, Any] = {
    "port": 9090,
    "host": "127.0.0.1",
    "hlil_cache_size": 500,
    "require_write_confirm": True,
    "batch_rename_confirm_threshold": 20,
    "log_level": "INFO",
    "auto_start": False,
}


def _config_path() -> Path:
    base = os.environ.get("BINARY_NINJA_USER_DIRECTORY")
    if base:
        p = Path(base) / "bn_mcp_server_config.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return Path.home() / ".binaryninja" / "bn_mcp_server_config.json"


def load_config() -> Dict[str, Any]:
    path = _config_path()
    with _lock:
        if not path.exists():
            cfg = dict(_DEFAULTS)
            cfg["bearer_token"] = secrets.token_hex(16)
            _save_unlocked(path, cfg)
            return cfg
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        cfg = {**_DEFAULTS, **data}
        if "bearer_token" not in cfg or not cfg["bearer_token"]:
            cfg["bearer_token"] = secrets.token_hex(16)
            _save_unlocked(path, cfg)
        return cfg


def _save_unlocked(path: Path, cfg: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def save_config(cfg: Dict[str, Any]) -> None:
    path = _config_path()
    with _lock:
        _save_unlocked(path, cfg)


def get_token() -> str:
    return str(load_config().get("bearer_token", ""))


def regenerate_token() -> str:
    path = _config_path()
    with _lock:
        cfg = load_config()
        cfg["bearer_token"] = secrets.token_hex(16)
        _save_unlocked(path, cfg)
        return cfg["bearer_token"]


def get_port() -> int:
    return int(load_config().get("port", 9090))


def get_host() -> str:
    return str(load_config().get("host", "127.0.0.1"))


def get_hlil_cache_size() -> int:
    return int(load_config().get("hlil_cache_size", 500))
