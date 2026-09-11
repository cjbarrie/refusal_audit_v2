#!/usr/bin/env python3
"""Fail-closed checks before committing or pushing the private repository.

The check is local and read-only. It never prints a matched credential value.
Warnings identify repository-size or dirty-tree issues that need a deliberate
decision; failures identify conditions that must be fixed before a push.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WARN_BYTES = 10 * 1024 * 1024
FAIL_BYTES = 100 * 1024 * 1024
TEXT_SUFFIXES = {
    ".csv", ".json", ".jsonl", ".md", ".py", ".r", ".R", ".sh",
    ".toml", ".txt", ".yaml", ".yml",
}
SECRET_PATTERNS = (
    re.compile(rb"sk-or-v1-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"hf_[A-Za-z0-9]{20,}"),
    re.compile(
        rb"(?i)(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|SECRET_KEY)"
        rb"\s*=\s*['\"][A-Za-z0-9_./+\-=]{20,}['\"]"
    ),
)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True
    )


def prospective_files() -> list[Path]:
    result = git("ls-files", "-co", "--exclude-standard", "-z")
    return sorted(
        path for item in result.stdout.split("\0") if item
        if (path := ROOT / item).is_file()
    )


def uses_lfs(rel: str) -> bool:
    result = git("check-attr", "filter", "--", rel).stdout.strip()
    return result.endswith(": lfs")


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    tracked = set(git("ls-files").stdout.splitlines())
    if ".env" in tracked:
        failures.append(".env is tracked")

    origin = git("remote", "get-url", "origin").stdout.strip()
    if not origin:
        failures.append("Git remote 'origin' is missing")

    files = prospective_files()
    large: list[tuple[int, str]] = []
    lfs_large: list[tuple[int, str]] = []
    secret_paths: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        size = path.stat().st_size
        if size >= WARN_BYTES:
            (lfs_large if uses_lfs(rel) else large).append((size, rel))
        if path.suffix not in TEXT_SUFFIXES or size > 5 * 1024 * 1024:
            continue
        content = path.read_bytes()
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            secret_paths.append(rel)

    too_large = [(size, rel) for size, rel in large if size >= FAIL_BYTES]
    if too_large:
        failures.append(
            "files at or above GitHub's 100 MiB limit: "
            + ", ".join(rel for _, rel in too_large)
        )
    if secret_paths:
        failures.append(
            "credential-like values found in prospective files (values suppressed): "
            + ", ".join(secret_paths)
        )
    if large:
        warnings.append(
            f"{len(large)} prospective files are at least 10 MiB; decide whether "
            "they belong in Git, Git LFS, or a versioned data deposit"
        )
    if lfs_large:
        lfs_check = subprocess.run(
            ["git", "lfs", "version"], cwd=ROOT, text=True, capture_output=True
        )
        if lfs_check.returncode != 0:
            failures.append("Git LFS is required by .gitattributes but is unavailable")

    dirty = git("status", "--porcelain=v1").stdout.splitlines()
    if dirty:
        warnings.append(f"working tree has {len(dirty)} changed paths")

    print("Private-repository preflight")
    print(f"prospective_files={len(files)}")
    print(f"origin_configured={'yes' if origin else 'no'}")
    for size, rel in sorted(large, reverse=True):
        print(f"[WARN] large_file={size / 1048576:.1f} MiB path={rel}")
    for size, rel in sorted(lfs_large, reverse=True):
        print(f"[INFO] lfs_file={size / 1048576:.1f} MiB path={rel}")
    for warning in warnings:
        print(f"[WARN] {warning}")
    for failure in failures:
        print(f"[FAIL] {failure}")
    if failures:
        return 1
    print("[PASS] no tracked .env, high-specificity credential match, or >=100 MiB file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
