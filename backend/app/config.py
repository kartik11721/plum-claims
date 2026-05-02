from __future__ import annotations
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def _find_policy_file() -> Path:
    candidates = [
        Path(os.environ.get("POLICY_FILE", "")),
        Path(__file__).parent.parent.parent / "policy_terms.json",
        Path(__file__).parent.parent.parent.parent / "policy_terms.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("policy_terms.json not found. Set POLICY_FILE env var.")


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    path = _find_policy_file()
    with open(path) as f:
        return json.load(f)


ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

AZURE_OPENAI_API_KEY: str = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT: str = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION: str = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_OPENAI_RESOURCE_NAME: str = os.environ.get("AZURE_OPENAI_RESOURCE_NAME", "")
AZURE_DEPLOYMENT_LLM: str = os.environ.get("AZURE_DEPLOYMENT_LLM", "")

DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./claims.db")
UPLOAD_DIR: Path = Path(os.environ.get("UPLOAD_DIR", "/tmp/plum_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
