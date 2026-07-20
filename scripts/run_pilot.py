"""
End-to-end pilot driver for the refusal audit v2 annotation run.

Stages (run any subset with --stages, default 'all'):
  sample    issue-level stratified subsample of each battery (sample_prompts.py)
  generate  subject-model responses for every (battery x language) sample file
  annotate  4-pass judge (engagement / ideology / moral) via gemini-2.5-flash-lite
  assemble  route regular-tier -> annotations_all.jsonl, boundary-tier ->
            annotations_<lang>_boundary.jsonl; write R-shape prompt metadata
  stance    optional Pass 4 stance coding on boundary prompts only

Everything is keyed off a single run directory (annotations/<run_id>/) so a
pilot is self-contained and reproducible. --dry-run prints the call budget
and exits without touching the API.

Example:
  python run_pilot.py --dry-run
  python run_pilot.py --stages sample
  python run_pilot.py --stages generate annotate assemble
"""
import argparse
import collections
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# PYTHONSAFEPATH is set in this environment, so the script's own directory is
# not auto-added to sys.path. Bootstrap it so sibling imports resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TEST_MODELS, SUPPORTED_LANGUAGES

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROMPTS_DIR = os.path.join(ROOT, "prompts")
ANN_DIR = os.path.join(ROOT, "annotations")

BATTERY_STEM = {"perennial": "full_prompts", "temporal": "temporal_prompts"}

TOPIC_DOMAIN_TO_CATEGORY = {
    "territorial_sovereignty": "territorial_sovereignty",
    "governance_democracy": "governance_democracy",
    "civil_rights_liberties": "civil_rights_liberties",
    "social_moral": "social_moral",
    "economic_policy": "economic_policy",
    "religion_state": "religion_state",
    "security_conflict": "security_conflict",
    "environment_energy": "environment_energy",
    "migration_nationalism": "migration_nationalism",
}

# Judge calls per response: Pass 1 always; Passes 2+3 only if engaged (~85% base
# rate). Boundary prompts get Pass 4 (stance) when that stage runs.
JUDGE_CALLS_ENGAGED = 3          # pass1 + pass2 + pass3
JUDGE_CALLS_REFUSED = 1          # pass1 only
ASSUMED_ENGAGE_RATE = 0.83       # from legacy KEY_FINDINGS

# --- USD cost model -------------------------------------------------------
# Per-token USD rates (input, output). OpenRouter rates snapshotted live from
# https://openrouter.ai/api/v1/models on 2026-07-19; re-pull with
# --refresh-pricing to overwrite these with current values at run time.
# The three MENA models are served via dedicated HF Inference Endpoints, which
# bill by GPU-HOUR while deployed, NOT per token. Their per-token rate is
# therefore set to (0, 0) here so they do not inflate the per-token USD estimate;
# their true cost is the endpoint uptime (see HF_ENDPOINT_HOURLY note below) and
# is reported separately, not folded into total_usd.
PRICING = {
    # openrouter subject models
    "openai/gpt-5.1":                 (1.25e-6, 1.0e-5),
    "anthropic/claude-opus-4.5":      (5.0e-6,  2.5e-5),
    "openai/gpt-4o":                  (2.5e-6,  1.0e-5),
    "x-ai/grok-4.3":                  (1.25e-6, 2.5e-6),
    "deepseek/deepseek-chat-v3.1":    (2.5e-7,  9.5e-7),
    "qwen/qwen3-max":                 (7.8e-7,  3.9e-6),
    "mistralai/mistral-large-2512":   (5.0e-7,  1.5e-6),
    # judges
    "google/gemini-2.5-flash-lite":   (1.0e-7,  4.0e-7),
    "openai/gpt-oss-120b":            (3.7e-8,  1.7e-7),
}
# MENA models run on dedicated HF Inference Endpoints (per-hour billing, not
# per-token), so their per-token generation rate is zero for the per-token model.
# The real endpoint cost is uptime-based and reported separately.
ENDPOINT_TOKEN_RATE = (0.0, 0.0)
# Indicative HF Inference Endpoint price for a single small-GPU replica
# (e.g. Nvidia L4 / A10G, ~7-10B model) in USD/hour. Documented ASSUMPTION used
# only for the uptime cost note; verify against the live HF endpoint console.
HF_ENDPOINT_HOURLY = 1.00

# ASSUMPTION: average tokens per call, by call type (input, output). Used only
# for the USD estimate; call COUNTS above are exact.
TOK = {
    "gen":    (140, 400),   # prompt in, model answer out
    "judge":  (620, 60),    # prompt+response in, short JSON verdict out
    "stance": (620, 60),    # boundary response in, stance JSON out
}


def _fetch_live_pricing():
    """Overwrite PRICING with current OpenRouter rates. Best-effort; keeps the
    snapshot on any failure. MENA endpoint models are not per-token billed and
    are left out of the per-token pricing table."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "refusal-audit-research/0.1"})
        data = json.load(urllib.request.urlopen(req, timeout=30))
        live = {m["id"]: m.get("pricing", {}) for m in data.get("data", [])}
        n = 0
        for mid in list(PRICING):
            if mid in live and live[mid].get("prompt") is not None:
                PRICING[mid] = (float(live[mid]["prompt"]), float(live[mid]["completion"]))
                n += 1
        print(f"  [pricing] refreshed {n} model rates from OpenRouter live API")
    except Exception as e:
        print(f"  [pricing] live refresh failed ({type(e).__name__}); using snapshot")


def _config_budget(n_issues, batteries, languages, models, pass1_only=False):
    """Return exact call counts + USD for one (models x languages) configuration.

    pass1_only reflects the full-run annotation mode: exactly one judge call per
    response (Pass 1 only, no ideology/MFT), and no stance stage -- so judge
    volume drops from ~2.7x gens to 1x gens and stance falls to zero.
    """
    n_reg = n_issues * 2
    n_bnd = n_issues * 2
    n_prompts = n_issues * 4
    cells = len(batteries) * len(languages)
    if pass1_only:
        per_resp = 1.0   # Pass 1 only -> one judge call per response
    else:
        per_resp = ASSUMED_ENGAGE_RATE * JUDGE_CALLS_ENGAGED + (1 - ASSUMED_ENGAGE_RATE) * JUDGE_CALLS_REFUSED

    gens = n_prompts * cells * len(models)
    judge = int(round(gens * per_resp))
    stance = 0 if pass1_only else n_bnd * cells * len(models)

    # USD: generations priced per subject model; judge/stance at their model rate.
    gi, go = TOK["gen"]
    gen_usd = 0.0
    for m in models:
        mid = m[1]
        # Endpoint (MENA) models bill per hour, not per token -> zero token rate.
        default_rate = ENDPOINT_TOKEN_RATE if m[3] == "hf-endpoint" else (0.0, 0.0)
        pin, pout = PRICING.get(mid, default_rate)
        gen_usd += (n_prompts * cells) * (gi * pin + go * pout)
    ji, jo = TOK["judge"]
    jpin, jpout = PRICING["google/gemini-2.5-flash-lite"]
    judge_usd = judge * (ji * jpin + jo * jpout)
    si, so = TOK["stance"]
    spin, spout = PRICING["openai/gpt-oss-120b"]
    stance_usd = stance * (si * spin + so * spout)

    # provider split of generation calls
    gens_or = n_prompts * cells * sum(1 for m in models if m[3] == "openrouter")
    gens_ep = n_prompts * cells * sum(1 for m in models if m[3] == "hf-endpoint")
    return {
        "n_models": len(models), "n_langs": len(languages), "cells": cells,
        "gens": gens, "gens_openrouter": gens_or, "gens_endpoint": gens_ep,
        "judge": judge, "stance": stance, "total_calls": gens + judge + stance,
        "gen_usd": gen_usd, "judge_usd": judge_usd, "stance_usd": stance_usd,
        "total_usd": gen_usd + judge_usd + stance_usd,
    }


def _run(cmd):
    print("  $", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=HERE)


def _truncate_stage_outputs(args, run_dir, stages):
    """--fresh: delete the per-(battery,language) output files for the
    resume-safe stages so they start from scratch instead of appending. Only
    touches files for stages actually requested; leaves sample output and
    already-completed sibling stages intact."""
    subdir = {"generate": "responses", "annotate": "ann", "stance": "stance"}
    removed = 0
    for st in stages:
        if st not in subdir:
            continue
        d = os.path.join(run_dir, subdir[st])
        for battery in args.batteries:
            for lang in args.languages:
                p = os.path.join(d, f"{battery}_{lang}.jsonl")
                if os.path.exists(p):
                    os.remove(p)
                    removed += 1
    print(f"--fresh: removed {removed} stage output file(s); will regenerate.")


def stage_sample(args):
    outdir = os.path.join(PROMPTS_DIR, "sampled")
    for battery in args.batteries:
        _run([sys.executable, "sample_prompts.py",
              "--battery", battery,
              "--n-issues", str(args.n_issues),
              "--seed", str(args.seed),
              "--prompts-dir", PROMPTS_DIR,
              "--out-dir", outdir])
    return outdir


def _sample_path(battery, lang):
    stem = BATTERY_STEM[battery]
    return os.path.join(PROMPTS_DIR, "sampled", f"{stem}_{lang}_sample.json")


def stage_generate(args, run_dir):
    resp_dir = os.path.join(run_dir, "responses")
    os.makedirs(resp_dir, exist_ok=True)
    for battery in args.batteries:
        for lang in args.languages:
            src = _sample_path(battery, lang)
            out = os.path.join(resp_dir, f"{battery}_{lang}.jsonl")
            _run([sys.executable, "generate_responses.py",
                  "--prompts", src, "--output", out,
                  "--workers", str(args.workers)])
    return resp_dir


def stage_annotate(args, run_dir):
    resp_dir = os.path.join(run_dir, "responses")
    ann_dir = os.path.join(run_dir, "ann")
    os.makedirs(ann_dir, exist_ok=True)
    for battery in args.batteries:
        for lang in args.languages:
            resp = os.path.join(resp_dir, f"{battery}_{lang}.jsonl")
            out = os.path.join(ann_dir, f"{battery}_{lang}.jsonl")
            cmd = [sys.executable, "annotation_pipeline.py",
                   "--responses", resp, "--output", out,
                   "--judge-model", args.judge,
                   "--workers", str(args.workers)]
            if args.pass1_only:
                cmd.append("--pass1-only")
            _run(cmd)
    return ann_dir


def stage_stance(args, run_dir):
    resp_dir = os.path.join(run_dir, "responses")
    stance_dir = os.path.join(run_dir, "stance")
    os.makedirs(stance_dir, exist_ok=True)
    for battery in args.batteries:
        for lang in args.languages:
            resp = os.path.join(resp_dir, f"{battery}_{lang}.jsonl")
            out = os.path.join(stance_dir, f"{battery}_{lang}.jsonl")
            # stance_coding filters to boundary internally? No -- it codes every
            # response. Restrict to boundary by passing only boundary responses
            # would require a filter; here we code all and let R subset by tier.
            _run([sys.executable, "stance_coding.py",
                  "--responses", resp, "--output", out,
                  "--judge", args.stance_judge,
                  "--workers", str(args.workers)])
    return stance_dir


def stage_assemble(args, run_dir):
    """Route annotation records into the R-contract file layout + metadata."""
    ann_dir = os.path.join(run_dir, "ann")
    out_dir = run_dir  # final surfaces live at run-dir root
    all_rows = []
    boundary_rows = collections.defaultdict(list)  # lang -> [rows]
    for battery in args.batteries:
        for lang in args.languages:
            path = os.path.join(ann_dir, f"{battery}_{lang}.jsonl")
            if not os.path.exists(path):
                continue
            # Resume-safe files are append-mode and may hold a stale error row
            # followed by a clean retry for the same key. Collapse last-wins on
            # (prompt_id, prompt_language, model), then drop error rows. This
            # also guards against any accidental duplicate clean rows.
            latest = {}
            for line in open(path):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                key = (rec.get("prompt_id"), rec.get("prompt_language"),
                       rec.get("model"))
                latest[key] = rec
            for rec in latest.values():
                if rec.get("error"):
                    continue  # excluded from all surfaces
                tier = rec.get("controversy_tier")
                if tier == "boundary_testing":
                    rec["dataset_type"] = "boundary"
                    boundary_rows[lang].append(rec)
                else:
                    rec["dataset_type"] = "base"
                    all_rows.append(rec)

    all_path = os.path.join(out_dir, "annotations_all.jsonl")
    with open(all_path, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  annotations_all.jsonl: {len(all_rows)} base rows")

    for lang, rows in sorted(boundary_rows.items()):
        bpath = os.path.join(out_dir, f"annotations_{lang}_boundary.jsonl")
        with open(bpath, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  annotations_{lang}_boundary.jsonl: {len(rows)} boundary rows")

    # R-shape prompt metadata (id, category, controversy_tier) per language,
    # combining both sampled batteries; topic_domain -> category.
    meta_dir = os.path.join(out_dir, "prompts_meta")
    os.makedirs(meta_dir, exist_ok=True)
    for lang in args.languages:
        prompts = []
        for battery in args.batteries:
            src = _sample_path(battery, lang)
            if not os.path.exists(src):
                continue
            data = json.load(open(src, encoding="utf-8"))
            for p in data["prompts"]:
                td = p.get("topic_domain")
                prompts.append({
                    "id": p["id"],
                    "category": TOPIC_DOMAIN_TO_CATEGORY.get(td, td),
                    "controversy_tier": p["controversy_tier"],
                    "topic_domain": td,
                    "battery": p.get("battery"),
                    "qid": p.get("qid"),
                    "region_focus": p.get("region_focus"),
                })
        mpath = os.path.join(meta_dir, f"test_prompts_{lang}.json")
        json.dump({"prompts": prompts}, open(mpath, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"  prompts_meta/test_prompts_{lang}.json: {len(prompts)} prompts")
    return out_dir


def cost_estimate(args):
    if getattr(args, "refresh_pricing", False):
        _fetch_live_pricing()

    n_reg = args.n_issues * 2
    n_bnd = args.n_issues * 2
    batts = args.batteries

    # Roster / language partitions for the comparison.
    or_models = [m for m in TEST_MODELS if m[3] == "openrouter"]        # 7 (US/CN/EU)
    baseline_langs = [l for l in args.languages if l != "ru"]           # drop Russian
    full_langs = args.languages                                         # all requested langs

    p1 = args.pass1_only
    configs = [
        ("baseline (%d OpenRouter models x %d langs)" % (len(or_models), len(baseline_langs)),
         _config_budget(args.n_issues, batts, baseline_langs, or_models, pass1_only=p1)),
        ("+Russian  (%d OpenRouter models x %d langs)" % (len(or_models), len(full_langs)),
         _config_budget(args.n_issues, batts, full_langs, or_models, pass1_only=p1)),
        ("+MENA/India (%d models x %d langs)" % (len(TEST_MODELS), len(full_langs)),
         _config_budget(args.n_issues, batts, full_langs, TEST_MODELS, pass1_only=p1)),
    ]

    print("=" * 78)
    print("PILOT CALL & COST BUDGET  (call counts EXACT; USD estimated)")
    print("=" * 78)
    print(f"  batteries      : {batts}")
    print(f"  issues/battery : {args.n_issues}  -> {n_reg} regular + {n_bnd} boundary prompts/lang/model")
    print(f"  full roster    : {len(TEST_MODELS)} models "
          f"(US:{sum(m[2]=='US' for m in TEST_MODELS)} CN:{sum(m[2]=='CN' for m in TEST_MODELS)} "
          f"EU:{sum(m[2]=='EU' for m in TEST_MODELS)} MENA:{sum(m[2]=='MENA' for m in TEST_MODELS)} "
          f"India:{sum(m[2]=='India' for m in TEST_MODELS)})")
    print(f"  full languages : {full_langs}")
    print(f"  judge / stance : {args.judge} / {args.stance_judge}")
    if args.pass1_only:
        print(f"  annotation     : PASS 1 ONLY (1 judge call/response; no ideology/MFT; no stance)")
    else:
        print(f"  annotation     : full (Pass 1 + ideology/MFT on engaged; + stance stage)")
        print(f"  engage rate    : {ASSUMED_ENGAGE_RATE:.0%} (engaged->{JUDGE_CALLS_ENGAGED} passes, "
              f"refused->{JUDGE_CALLS_REFUSED})")
    print("-" * 78)
    hdr = f"{'configuration':<44}{'gens':>9}{'judge':>9}{'stance':>8}{'USD':>8}"
    print(hdr)
    print("-" * 78)
    for name, b in configs:
        print(f"{name:<44}{b['gens']:>9,}{b['judge']:>9,}{b['stance']:>8,}{b['total_usd']:>8.2f}")
    print("-" * 78)
    base, rus, mena = [c[1] for c in configs]
    n_mena = sum(m[2] == "MENA" for m in TEST_MODELS)
    print(f"  marginal cost of Russian (5->6 lang): "
          f"+{rus['total_calls']-base['total_calls']:,} calls, +${rus['total_usd']-base['total_usd']:.2f}")
    print(f"  marginal cost of MENA (7->{len(TEST_MODELS)} models): "
          f"+{mena['total_calls']-rus['total_calls']:,} calls, +${mena['total_usd']-rus['total_usd']:.2f} (per-token)")
    print(f"  full expanded matrix TOTAL          : "
          f"{mena['total_calls']:,} calls, ~${mena['total_usd']:.2f} (per-token, OpenRouter only)")
    print(f"    - via OpenRouter (billed) gens     : {mena['gens_openrouter']:,}")
    print(f"    - via HF endpoints (MENA) gens     : {mena['gens_endpoint']:,}  "
          f"[{n_mena} endpoints billed by GPU-hour, ~${HF_ENDPOINT_HOURLY:.2f}/hr each while deployed]")
    print("=" * 78)

    # Write artifact for the record.
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assumptions": {
            "engage_rate": ASSUMED_ENGAGE_RATE,
            "judge_calls_engaged": JUDGE_CALLS_ENGAGED,
            "judge_calls_refused": JUDGE_CALLS_REFUSED,
            "tokens_per_call": TOK,
            "pricing_usd_per_token": PRICING,
            "mena_via_hf_endpoints_billed_per_gpu_hour": True,
            "hf_endpoint_hourly_usd_assumption": HF_ENDPOINT_HOURLY,
            "n_issues": args.n_issues, "batteries": batts,
        },
        "configurations": {name: b for name, b in configs},
    }
    bud_path = os.path.join(ROOT, "docs", "budget_estimate.json")
    os.makedirs(os.path.dirname(bud_path), exist_ok=True)
    json.dump(out, open(bud_path, "w"), indent=2)
    print(f"  wrote {bud_path}")


def main():
    ap = argparse.ArgumentParser(description="Refusal-audit v2 pilot driver")
    ap.add_argument("--stages", nargs="+",
                    default=["all"],
                    choices=["all", "sample", "generate", "annotate", "assemble", "stance"])
    ap.add_argument("--batteries", nargs="+", default=["perennial", "temporal"],
                    choices=["perennial", "temporal"])
    ap.add_argument("--languages", nargs="+", default=SUPPORTED_LANGUAGES)
    ap.add_argument("--n-issues", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260712)
    ap.add_argument("--judge", default="google/gemini-2.5-flash-lite")
    ap.add_argument("--stance-judge", default="openai/gpt-oss-120b")
    ap.add_argument("--workers", type=int, default=8,
                    help="Concurrent API workers per stage script (default: 8). "
                         "Raise for faster wall-time; lower if you hit OpenRouter "
                         "rate limits (HTTP 429).")
    ap.add_argument("--pass1-only", action="store_true",
                    help="Annotate stage: run only Pass 1 (engagement + refusal "
                         "justification), skipping the ideology and moral-foundations "
                         "passes. This is the full-run mode (the study's target is "
                         "refusal + nature of refusal). Default off; the pilot keeps "
                         "all passes.")
    ap.add_argument("--run-id", default=None, help="run dir name under annotations/ (default: pilot_<UTC>)")
    ap.add_argument("--dry-run", action="store_true", help="print call budget and exit")
    ap.add_argument("--refresh-pricing", action="store_true",
                    help="pull current per-token rates from the OpenRouter models "
                         "API before estimating USD (else use the code snapshot)")
    ap.add_argument("--fresh", action="store_true",
                    help="truncate the per-(battery,language) output files for the "
                         "requested generate/annotate/stance stages before running, "
                         "forcing a clean redo instead of resuming. Without this flag, "
                         "re-running the same --run-id RESUMES (skips clean rows, "
                         "retries errored ones).")
    ap.add_argument("--resume", action="store_true",
                    help="explicitly continue an existing run dir (annotations/<run-id>/): "
                         "skips clean rows, retries errored ones. REQUIRED to run against a "
                         "run dir that already contains output — otherwise the run refuses to "
                         "start, to protect against accidentally writing into the wrong run. "
                         "Mutually exclusive with --fresh.")
    args = ap.parse_args()

    if args.resume and args.fresh:
        ap.error("--resume and --fresh are mutually exclusive: --resume continues an "
                 "existing run, --fresh truncates it. Pick one.")

    cost_estimate(args)
    if args.dry_run:
        return

    run_id = args.run_id or ("pilot_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    run_dir = os.path.join(ANN_DIR, run_id)

    # Guard: refuse to start against a run dir that already holds output, unless the
    # user explicitly opts in with --resume (continue) or --fresh (truncate & redo).
    # "Holds output" = any entry other than the pilot_config.json we write ourselves.
    if os.path.isdir(run_dir):
        prior = [f for f in os.listdir(run_dir) if f != "pilot_config.json"]
        if prior and not (args.resume or args.fresh):
            preview = ", ".join(sorted(prior)[:6]) + (" ..." if len(prior) > 6 else "")
            sys.exit(
                f"ERROR: run dir already exists with output: {run_dir}\n"
                f"       contains: {preview}\n"
                f"       Pass --resume to continue it (skip clean rows, retry errors),\n"
                f"       --fresh to truncate stage outputs and redo, or choose a new --run-id.")

    os.makedirs(run_dir, exist_ok=True)
    json.dump(vars(args), open(os.path.join(run_dir, "pilot_config.json"), "w"), indent=2)
    print(f"RUN DIR: {run_dir}\n")

    stages = args.stages
    if "all" in stages:
        stages = ["sample", "generate", "annotate", "assemble"]

    if args.fresh:
        _truncate_stage_outputs(args, run_dir, stages)

    for st in stages:
        print(f"\n===== STAGE: {st} =====")
        {"sample": stage_sample,
         "generate": lambda a: stage_generate(a, run_dir),
         "annotate": lambda a: stage_annotate(a, run_dir),
         "assemble": lambda a: stage_assemble(a, run_dir),
         "stance": lambda a: stage_stance(a, run_dir)}[st](args)

    print(f"\nDONE. Pilot outputs under: {run_dir}")


if __name__ == "__main__":
    main()
