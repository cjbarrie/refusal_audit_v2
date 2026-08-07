#!/usr/bin/env python3
"""Project the text of every refusal into 2D with UMAP.

WHAT THIS IS FOR. The judge assigns each refusal one of seven justification
codes (A-G). Those codes had the weakest inter-judge agreement of any construct
in the study, which is why no canonical estimand rests on them. This projection
asks the prior question: do refusals written for different stated reasons
actually *look* different? If the A-G regions overlap completely in refusal-text
space, the taxonomy is not recovering distinctions that exist in the text.

SEMANTIC BY DEFAULT, STILL NO API SPEND. Text is embedded with a local
sentence-transformers model, so the space is semantic: two refusals giving the
same reason in different words land near each other, which is the question this
figure asks. `--encoder tfidf` falls back to the lexical TF-IDF -> SVD
representation, kept as a contrast -- a grouping that survives under both is not
an artefact of shared boilerplate. Model weights download once and cache; no API
is called.

ONLY THE OPENING OF EACH REFUSAL IS EMBEDDED (--max-chars, default 800). The
stated reason comes first; the rest is usually hedging, and letting a
1,400-character response dominate its own embedding buries the justification.

LANGUAGE. English only by default. TF-IDF across scripts separates Arabic from
English on tokenisation alone, which would produce a figure about writing
systems rather than about refusals. `--languages` overrides this deliberately.

Writes coordinates to pipeline/estimates/u01_refusal_umap.csv; the figure is
drawn in R (pipeline/57_refusal_umap_figure.R) so plotting stays separate from
computation, as everywhere else in this repo.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Judge codebook for Pass 1's refusal_justification field. These labels and the
# five-group collapse are the repo's, taken from the archived v1 support script
# (pipeline/archive/precanonical_v1/21_estimates_support.R) so this figure and
# e13/e13b name the same things. F ("none given") and G ("other") are kept
# SEPARATE: folding them together produced a single bar that meant two
# incompatible things and hid a measurement failure mode.
CODE_LABEL = {
    "A": "A neutrality",
    "B": "B complexity",
    "C": "C harm avoidance",
    "D": "D expertise limitation",
    "E": "E user autonomy",
    "F": "F none given",
    "G": "G other",
}
# The five plotted groups; names match PAL_REASON in pipeline/_theme.R exactly,
# so the figure needs no colour literals of its own. B/D/E are thin (single
# digits in the English refusal set) and are one conceptual family.
CODE_GROUP = {"A": "neutrality", "C": "harm", "B": "epistemic",
              "D": "epistemic", "E": "epistemic",
              "F": "none given", "G": "other"}

REGION_TO_JURIS = {"China": "CN", "Arab": "MENA", "India": "India",
                   "US": "US", "Europe": "EU"}


def load_annotations(run_dir: Path) -> pd.DataFrame:
    """Every annotated row, base tier plus all boundary-tier files."""
    files = [run_dir / "annotations_all.jsonl"]
    files += sorted(run_dir.glob("annotations_*_boundary.jsonl"))
    rows = []
    for f in files:
        if not f.exists():
            continue
        tier = "boundary" if "_boundary" in f.name else "regular"
        with f.open() as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("engagement_code") is None or r["engagement_code"] < 4:
                    continue
                rows.append({
                    "prompt_id": r["prompt_id"],
                    "prompt_language": r["prompt_language"],
                    "model": r["model"],
                    "engagement_code": r["engagement_code"],
                    "code": r.get("refusal_justification") or "G",
                    "other_text": r.get("refusal_justification_other") or "",
                    "tier": tier,
                })
    df = pd.DataFrame(rows)
    # A (prompt_id, language, model) can appear in both a base and a boundary
    # file; keep one row so a duplicated refusal is not double-plotted.
    return df.drop_duplicates(subset=["prompt_id", "prompt_language", "model"])


def load_responses(run_dir: Path, languages: set[str]) -> pd.DataFrame:
    rows = []
    for f in sorted((run_dir / "responses").glob("*.jsonl")):
        with f.open() as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("prompt_language") not in languages:
                    continue
                rows.append({
                    "prompt_id": r["prompt_id"],
                    "prompt_language": r["prompt_language"],
                    "model": r["model"],
                    "response_text": r.get("response_text") or "",
                    "issue_id": r.get("issue_id"),
                    "region_focus": r.get("region_focus"),
                    "topic_domain": r.get("topic_domain"),
                    "battery": r.get("battery"),
                })
    df = pd.DataFrame(rows)
    # The response files carry retry attempts as extra rows for the same
    # (prompt_id, language, model): an empty-text failure plus the successful
    # generation, in no guaranteed order. Non-English files are mostly these
    # (hi has 29,831 duplicate rows against 29,877 empty-text rows). Keeping the
    # FIRST row would silently keep the failed attempt, so keep the longest.
    n_before = len(df)
    df = (df.assign(_len=df["response_text"].str.len())
            .sort_values("_len", ascending=False)
            .drop_duplicates(subset=["prompt_id", "prompt_language", "model"])
            .drop(columns="_len"))
    if n_before != len(df):
        print(f"collapsed {n_before - len(df):,} retry rows "
              f"(kept the longest text per prompt x language x model)")
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="annotations/full_v1")
    ap.add_argument("--languages", default="en",
                    help="comma-separated; default en (see module docstring)")
    ap.add_argument("--out", default="pipeline/estimates/u01_refusal_umap.csv")
    ap.add_argument("--seed", type=int, default=20260807)
    ap.add_argument("--n-neighbors", type=int, default=25)
    ap.add_argument("--min-dist", type=float, default=0.08)
    ap.add_argument("--svd-dim", type=int, default=100)
    ap.add_argument("--encoder", default="semantic",
                    choices=["semantic", "tfidf"])
    ap.add_argument("--st-model",
                    default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                    help="one encoder for every language, so panels are comparable")
    ap.add_argument("--max-chars", type=int, default=800)
    ap.add_argument("--min-chars", type=int, default=15,
                    help="drop refusals too short to carry lexical signal")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    languages = {s.strip() for s in args.languages.split(",") if s.strip()}

    ann = load_annotations(run_dir)
    print(f"refusals annotated (all languages): {len(ann):,}")
    resp = load_responses(run_dir, languages)
    print(f"responses loaded ({'/'.join(sorted(languages))}): {len(resp):,}")

    df = ann.merge(resp, on=["prompt_id", "prompt_language", "model"], how="inner")
    print(f"refusals with response text: {len(df):,}")

    short = df["response_text"].str.len() < args.min_chars
    if short.any():
        print(f"dropping {short.sum():,} refusals under {args.min_chars} chars")
    df = df[~short].reset_index(drop=True)
    if df.empty:
        print("nothing to project", file=sys.stderr)
        return 1

    print("justification codes:",
          ", ".join(f"{k}={v}" for k, v in
                    sorted(Counter(df["code"]).items(), key=lambda x: -x[1])))

    from sklearn.preprocessing import normalize

    multilingual = len(languages) > 1
    texts = df["response_text"].str.slice(0, args.max_chars).tolist()

    if args.encoder == "semantic":
        from sentence_transformers import SentenceTransformer
        print(f"encoder: {args.st_model} (local)")
        Z = SentenceTransformer(args.st_model).encode(
            texts, batch_size=64, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=True)
        rep = f"sbert:{args.st_model.split('/')[-1]}@{args.max_chars}chars"
        print(f"embeddings: {Z.shape[0]:,} x {Z.shape[1]}")
    else:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        # Word tokens for one language; character n-grams when several scripts
        # share the space, because the default token pattern needs whitespace
        # and would pass a whole Chinese sentence through as a single token.
        if multilingual:
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                  min_df=5, max_df=0.6, sublinear_tf=True,
                                  lowercase=True)
        else:
            vec = TfidfVectorizer(strip_accents="unicode", lowercase=True,
                                  ngram_range=(1, 2), min_df=5, max_df=0.6,
                                  sublinear_tf=True, stop_words=None)
        X = vec.fit_transform(texts)
        print(f"tf-idf: {X.shape[0]:,} x {X.shape[1]:,}")
        dim = min(args.svd_dim, X.shape[1] - 1)
        Z = normalize(TruncatedSVD(n_components=dim,
                                   random_state=args.seed).fit_transform(X))
        rep = ("tfidf-char_wb(3,5)" if multilingual
               else "tfidf-word(1,2)") + f"->svd{dim}"

    import umap

    # Cosine metric: refusal texts vary a lot in length, and cosine is what the
    # TF-IDF/SVD representation is built for.
    reducer = umap.UMAP(n_components=2, n_neighbors=args.n_neighbors,
                        min_dist=args.min_dist, metric="cosine",
                        random_state=args.seed, verbose=False)
    emb = reducer.fit_transform(Z)
    df["umap_x"], df["umap_y"] = emb[:, 0], emb[:, 1]

    df["code_label"] = df["code"].map(CODE_LABEL).fillna("G other")
    df["reason_group"] = df["code"].map(CODE_GROUP).fillna("other")
    df["jurisdiction"] = df["region_focus"].map(REGION_TO_JURIS)
    df["n_chars"] = df["response_text"].str.len()

    # A neighbourhood-purity diagnostic, so the figure is not read by eye alone:
    # among each point's k nearest neighbours in the projected space, what share
    # carry the same justification code? Compared against the share expected if
    # codes were scattered at random (the prevalence-weighted baseline).
    from sklearn.neighbors import NearestNeighbors
    k = 15
    nn = NearestNeighbors(n_neighbors=k + 1).fit(emb)
    _, idx = nn.kneighbors(emb)
    codes = df["code"].to_numpy()
    same = np.array([(codes[row[1:]] == codes[row[0]]).mean() for row in idx])
    p = df["code"].value_counts(normalize=True)
    baseline = float((p ** 2).sum())
    # Same statistic on the five plotted groups, since that is what the figure
    # actually shows -- reporting purity on 7 codes next to a 5-group figure
    # would be quoting a number the reader cannot see.
    grp = df["reason_group"].to_numpy()
    same_g = np.array([(grp[row[1:]] == grp[row[0]]).mean() for row in idx])
    pg = df["reason_group"].value_counts(normalize=True)
    baseline_g = float((pg ** 2).sum())
    print(f"\nneighbourhood purity (k={k}), 7 codes : {same.mean():.3f} "
          f"vs {baseline:.3f} at random")
    print(f"neighbourhood purity (k={k}), 5 groups: {same_g.mean():.3f} "
          f"vs {baseline_g:.3f} at random")
    df["neighbour_purity"] = same
    df["neighbour_purity_group"] = same_g

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    keep = ["prompt_id", "prompt_language", "model", "issue_id", "region_focus",
            "jurisdiction", "topic_domain", "tier", "battery", "engagement_code",
            "code", "code_label", "reason_group", "n_chars", "neighbour_purity",
            "neighbour_purity_group",
            "umap_x", "umap_y"]
    df[keep].assign(
        seed=args.seed, n_neighbors=args.n_neighbors, min_dist=args.min_dist,
        metric="cosine", representation=rep, encoder=args.encoder,
        max_chars=args.max_chars,
        purity_k=k, purity_observed=round(float(same.mean()), 4),
        purity_baseline=round(baseline, 4),
        purity_group_observed=round(float(same_g.mean()), 4),
        purity_group_baseline=round(baseline_g, 4),
    ).to_csv(out, index=False)
    print(f"wrote {out} ({len(df):,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
