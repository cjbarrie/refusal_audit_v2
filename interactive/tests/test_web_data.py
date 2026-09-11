"""Contract checks for the generated standalone-web assets."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "interactive" / "web" / "public" / "data"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_web_assets_match_their_manifest():
    metadata = json.loads((DATA / "metadata.json").read_text(encoding="utf-8"))
    prompts = json.loads((DATA / "prompts.json").read_text(encoding="utf-8"))
    refusals = json.loads((DATA / "refusals.json").read_text(encoding="utf-8"))

    assert len(prompts) == metadata["counts"]["prompts"] == 2496
    assert len(refusals) == metadata["counts"]["genuine_refusals"]
    assert len({row["prompt_id"] for row in prompts}) == 2496
    assert all(row["response_text"] for row in refusals)
    assert all(
        all(row[field] is not None for field in ("umap_3d_x", "umap_3d_y", "umap_3d_z"))
        for row in prompts
    )
    assert digest(DATA / "prompts.json") == metadata["output_hashes"]["prompts_json"]
    assert digest(DATA / "refusals.json") == metadata["output_hashes"]["refusals_json"]


def test_web_assets_exclude_sensitive_fields():
    refusals = json.loads((DATA / "refusals.json").read_text(encoding="utf-8"))
    forbidden = ("api_key", "reasoning", "account", "provider_request_id")
    assert not any(any(fragment in key.lower() for fragment in forbidden) for key in refusals[0])
