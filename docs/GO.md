# GO — Full-Run Launch Runbook

**Purpose.** One page to press GO on the full response-generation + annotation
run once OpenRouter credits are in place. Everything here runs on **your
machine** (the sandbox holds no credentials and cannot spend). Commands are
copy-paste ready from the repo root.

```
cd /Users/christopherbarrie/Dropbox/nyu_projects/refusal_audit_v2
conda activate refusal-v2      # py3.13; matplotlib/pandas/numpy/openai/pyyaml
```

---

## 0. Credential checklist

| Stage | Needs | Env var | Without it |
|-------|-------|---------|------------|
| Subject generation (7 serverless models) | OpenRouter credits | `OPENROUTER_API_KEY` | run cannot proceed |
| Judge (Pass 1) + stance (pilot only) | OpenRouter | `OPENROUTER_API_KEY` | annotation cannot proceed |
| MENA + India arm (4 models) | HF token **and** each endpoint deployed | `HF_TOKEN` + `ALLAM_ENDPOINT_URL`, `FALCON3_ENDPOINT_URL`, `JAIS_ENDPOINT_URL`, `SARVAM_ENDPOINT_URL` | roster silently drops to the 7 OpenRouter models |

The credentials live in `.env` (present, git-ignored). The roster is assembled
**at import time**: each endpoint model joins `TEST_MODELS` only if its
`*_ENDPOINT_URL` is set. So a run with the 4 endpoints down is a valid 7-model
run — no code change needed, the budget and outputs just cover 7 models.

---

## 1. Endpoint readiness

**Wikipedia (question sourcing) — DONE.** The batteries are frozen; no live
Wikipedia calls happen during the run. (All 6 editions were verified reachable
when the batteries were built: en/zh/ja/id/ar/ru.)

**LLM providers — verify at launch:**

```
python sourcing/preflight_providers.py
```

Probes OpenRouter (a live `openai/gpt-4o-mini` call) and each HF endpoint
(`HF_TOKEN` + `*_ENDPOINT_URL`). Reports PASS / FAIL / SKIP per provider. A SKIP
on the HF block just means the MENA/India arm is off for this run.

---

## 2. Frozen inputs (do not regenerate)

| Battery | File stem | Issues | Prompts/lang | Tiers |
|---------|-----------|--------|--------------|-------|
| perennial | `prompts/full_prompts_{lang}.json` | 387 | 1,548 | 774 regular + 774 boundary |
| temporal | `prompts/temporal_prompts_{lang}.json` | 799 | 3,199 | 1,599 regular + 1,600 boundary |
| **total** | | | **4,747 / lang** | |

Languages (7): `en zh ja id ar ru hi`. All present for both batteries.

---

## 3. Cost estimate

Regenerate any time with the dry-run (writes `docs/budget_estimate.json`):

```
python scripts/run_pilot.py --dry-run --stages generate annotate assemble --pass1-only \
  --batteries perennial temporal --languages en zh ja id ar ru hi \
  --n-issues 1000 --run-id full_v1
```

Call counts are **exact** (read from the frozen battery files); USD is estimated
from per-token pricing in the script. Full run = **Pass 1 only** (one judge call
per response; no ideology/MFT; no stance).

**7 OpenRouter models × 7 languages (Pass-1-only):**

| Item | Count | Cost |
|------|-------|------|
| Generations (billed, per-token) | 232,603 | included below |
| Judge calls (Pass 1, 1 per response) | 232,603 | included below |
| **OpenRouter token spend** | 465,206 calls | **~$789** |

**Adding the 4 HF-endpoint models (→ 11-model roster):**

| Item | Count | Billing |
|------|-------|---------|
| Endpoint generations | 132,916 | **GPU-hour**, ~$1.00/hr per endpoint while deployed (not per token) |
| Judge calls on those responses | 132,916 | per-token (OpenRouter, folded into judge cost) |
| **All-11 generations** | 365,519 | |

So the OpenRouter token bill is **~$789** for the 7-model run; the endpoint arm
adds GPU-hour cost (deploy → run → **tear down**) plus a modest judge-token
increment for the extra 132,916 responses. Budget a headroom buffer above $789
for output-length variance.

> The earlier $1,330 figure was an artifact of the budget script pricing
> `n_issues×4 = 8,000` prompts/battery. It now reads the real frozen counts
> (4,747/lang total). `budget_estimate.json` is current.

---

## 4. Launch sequence

### Step 1 — Smoke test (small spend, ~$1)
Exercises every stage end-to-end on 2 issues, 4 languages, all passes incl.
stance. Disjoint run-id so it never collides with the real run.

```
python scripts/run_pilot.py \
  --stages sample generate annotate assemble stance \
  --batteries perennial --languages en ar ru hi \
  --n-issues 2 --run-id smoke_v1
```
Inspect `annotations/smoke_v1/` for populated response + annotation files.

### Step 2 — Dry-run the real config (no spend)
The command in §3. Confirm the printed roster (7 or 11 models), languages, and
the ~$789 figure look right.

### Step 3 — Full run (main spend)
```
python scripts/run_pilot.py \
  --stages generate annotate assemble --pass1-only \
  --batteries perennial temporal --languages en zh ja id ar ru hi \
  --n-issues 1000 --run-id full_v1 --seed 20260712 --workers 8
```

Notes:
- `--n-issues 1000` caps issues/battery; both batteries have fewer (387 / 799),
  so **all** issues are used. The cap is just a ceiling.
- **No `sample` stage and no `stance` stage** — the full run uses the frozen
  batteries directly and is Pass-1-only.
- `--seed 20260712` and `--workers 8` are the pinned defaults.
- If the 4 HF endpoints are deployed (`*_ENDPOINT_URL` set), the roster is 11
  and the endpoint models are generated automatically. **Tear the endpoints
  down when the run finishes** — they bill by the hour while up.

---

## 5. Resume / restart behavior

- The run **refuses to start** if `annotations/full_v1/` already has output,
  unless you pass `--resume` (continue, skipping completed
  battery×language cells) or `--fresh` (delete stage outputs and regenerate).
  `--resume` and `--fresh` are mutually exclusive.
- Generation and annotation are **resume-safe**: each `(battery, language)`
  writes its own `.jsonl`; re-running skips complete cells and retries only
  errored rows. A mid-run interruption is safe — just re-launch with `--resume`.

---

## 6. Post-run verification

```
# Response + annotation files present for all 7 languages, both batteries:
ls annotations/full_v1/responses/ annotations/full_v1/ann/

# Load-check the R analysis layer against the real run:
REFUSAL_RUN_DIR=annotations/full_v1 Rscript pipeline/01_data_loading.R
```
Confirm the loader picks up all languages incl. `ru` and `hi` (factor levels
`en zh ja id ar ru hi`) and writes `pipeline/data_clean.RData` without missing-
file warnings for the boundary files.

---

## 7. GitHub push (separate, no spend)

The sandbox cannot create a `.git` dir or authenticate. On your machine:

```
brew install gh && gh auth login      # once
bash push_to_github.sh                 # git init → cjbarrie identity → secret gate → gh repo create refusal_audit --private --push
```
The script aborts if `.env` or any secret is staged.
