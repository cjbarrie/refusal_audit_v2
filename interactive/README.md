# Refusal explorers

This directory contains two read-only interfaces to the promoted release's Luna
v2.4 genuine-refusal labels. `app.py` is the compact Streamlit verification
interface. `web/` is the standalone Refusal Observatory: a full-screen 3-D/2-D
semantic atlas intended for exploratory use and eventual public presentation.
Historical human-review and adjudication pages remain archived after their
ledgers were frozen under `annotations/`.

## Inputs and build

From the repository root:

```bash
python3.9 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python interactive/build_data.py
```

`build_data.py`:

1. resolves the promoted release from
   `pipeline/estimates/canonical/c00_manifest.csv`;
2. verifies that manifest against its immutable release;
3. reads that release's fixed `c22_prompt_umap_coordinates.csv` (2,496 prompt
   points) and never fits an embedding or UMAP;
4. loads the exact response frame stored inside that immutable release;
5. assembles the original and seven expansion models' response text using the
   last-valid-record rule, and verifies every expansion JSONL against the hash
   that supplied its frozen Luna batch;
6. writes ignored `interactive/data/{umap_points,responses}.parquet` plus a
   hash/count manifest.

For the current 18-model contract the expected result is 224,544 response rows,
18 models and 2,496 prompt points. The build fails on a changed manifest or
source hash, duplicate key, missing prompt/response text, missing annotation or
unexpected row count. It will therefore continue to show the old promoted
release until a new release is accepted and promoted.

## Run

```bash
python -m streamlit run interactive/app.py --server.address 127.0.0.1
```

All prompt points are visible as gray context. Red overlays indicate at least
one v2.4 genuine refusal after the selected filters. Selecting a red point shows
the prompt, full response and decomposed v2.4 fields. Arabic text is rendered
right-to-left. The app makes no network calls and writes no labels.

## Standalone Refusal Observatory

Build its static browser assets from the same verified local data:

```bash
python interactive/build_web_data.py
```

This fits one separate three-dimensional UMAP to the same frozen
512-dimensional English-prompt embeddings used by the canonical two-dimensional
map. The seed (`20260809`), distance metric (`cosine`), neighbours (`25`) and
minimum distance (`0.15`) are fixed. Outcomes never enter the fit, and filters
never move points. The 3-D projection is an exploratory locator, not an
estimand. The 2-D toggle continues to use the canonical `c22` coordinates.

Run the standalone site:

```bash
cd interactive/web
npm install
npm run dev -- --host 127.0.0.1
```

The current page loads all 2,496 prompt points and only the 6,127
genuine-refusal response records in `canon_024`. Gray context points remain
hoverable and selectable. Selecting a point opens its prompt, matching
responses, refusal evidence and v2.4 coding without leaving the constellation.
The publication JSON is versioned through Git LFS so a GitHub Pages build uses
the exact reviewed browser dataset rather than regenerating it from untracked
raw annotations.

### GitHub Pages publication

`npm run build:pages` produces a fully static bundle under `web/dist/pages`.
The workflow `.github/workflows/publish-refusal-observatory.yml` places that
bundle under an unlisted route and deploys it from `main`. The page includes a
`noindex` instruction and the deployment root disallows web crawlers. These are
discovery deterrents, not access control: anyone who obtains the full URL can
read the published prompts and genuine-refusal responses.

To update the public site after promoting a new canonical release:

```bash
python interactive/build_data.py
python interactive/build_web_data.py
cd interactive/web
npm run build:pages
```

Review the local build, commit the three `public/data/*.json` LFS pointers and
site changes, then merge to `main`. The Pages workflow runs automatically. It
can also be started manually from the repository's Actions tab.

## Test

```bash
python -m pytest -q interactive/tests
cd interactive/web && npm run build
```

Generated data and logs are ignored. They must never contain API keys, endpoint
URLs, account identifiers or model reasoning traces.
