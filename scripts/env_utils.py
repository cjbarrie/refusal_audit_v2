"""
Minimal `.env` loader and shared utilities for local development.

Avoids third-party deps (e.g., python-dotenv). Intended for loading secrets like
OPENROUTER_API_KEY from `refusal_audit/.env` or the current working directory.

Also provides shared helper functions used across multiple scripts:
- get_openrouter_client(): Initializes OpenAI client for OpenRouter API
- iter_jsonl(): Iterates over JSONL files yielding parsed records
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Union


def _parse_env_line(line: str) -> Optional[tuple[str, str]]:
    raw = line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        return None

    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    # Strip surrounding single/double quotes
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]

    return key, value


def _candidate_paths(extra_paths: Optional[Iterable[Path]] = None) -> list[Path]:
    scripts_dir = Path(__file__).resolve().parent
    repo_dir = scripts_dir.parent
    home_dir = Path.home()

    candidates = [
        Path.cwd() / ".env",
        repo_dir / ".env",
        home_dir / ".config" / "refusal_audit" / ".env",
        home_dir / ".config" / "openrouter" / ".env",
        home_dir / ".openrouter.env",
    ]

    if extra_paths:
        candidates.extend(list(extra_paths))

    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def load_env_from_file(
    env_path: Optional[Path] = None,
    *,
    override: bool = False,
    extra_paths: Optional[Iterable[Path]] = None,
) -> Dict[str, str]:
    """
    Load environment variables from a `.env` file if present.

    Does not overwrite existing environment variables unless `override=True`.
    Returns a dict of variables read (whether or not they were set due to override=False).
    """
    paths = [env_path] if env_path is not None else _candidate_paths(extra_paths=extra_paths)
    loaded: Dict[str, str] = {}

    for path in paths:
        try:
            if not path.exists() or not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                parsed = _parse_env_line(line)
                if not parsed:
                    continue
                key, value = parsed
                loaded[key] = value
                if override or key not in os.environ:
                    os.environ[key] = value
            break
        except OSError:
            continue

    return loaded


def get_openrouter_client():
    """
    Initialize and return an OpenAI client configured for OpenRouter.

    Automatically loads environment variables from .env file and retrieves
    OPENROUTER_API_KEY.

    Returns:
        OpenAI client configured for OpenRouter API

    Raises:
        ValueError: If OPENROUTER_API_KEY is not set
        ImportError: If openai package is not installed
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package required: pip install openai")

    load_env_from_file()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable not set. "
            "Create a .env file with OPENROUTER_API_KEY=your-key"
        )

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def iter_jsonl(path: Union[str, Path]) -> Iterator[Dict]:
    """
    Iterate over a JSONL file, yielding parsed JSON records.

    Args:
        path: Path to the JSONL file

    Yields:
        Parsed JSON objects (dicts) from each line

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If a line contains invalid JSON
    """
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
