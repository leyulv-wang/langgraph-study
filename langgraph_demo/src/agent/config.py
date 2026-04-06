from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    github: Dict[str, Any]
    news: Dict[str, Any]
    output: Dict[str, Any]
    limits: Dict[str, Any]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(config_path: Optional[str] = None) -> AppConfig:
    load_dotenv()
    path = Path(config_path) if config_path else project_root() / "config" / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(
        github=dict(data.get("github", {})),
        news=dict(data.get("news", {})),
        output=dict(data.get("output", {})),
        limits=dict(data.get("limits", {})),
    )


def get_env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default))

