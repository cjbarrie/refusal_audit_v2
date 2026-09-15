# Refusal Atlas website

This directory contains the static publication site for the interactive refusal atlas. It is a presentation layer over frozen pipeline outputs; it does not estimate outcomes or refit the semantic geometry.

## Page structure

1. **Overview** introduces the project, authors and current data coverage.
2. **Atlas** provides the full 3-D/2-D semantic explorer with jurisdiction, model, language, domain and text filters.
3. **Models** shows a lightweight rotating projection for every model. Jurisdiction tabs narrow the gallery. Selecting a panel opens a full-screen interactive view for that model.
4. **Methods** explains the fixed geometry, the genuine-refusal outcome and the limits of interpretation.
5. **Funding & credits** identifies Christopher Barrie and Joshua Tucker as authors and presents the NYU and Schmidt Foundation partner marks.

The small gallery previews use the browser's 2-D canvas and a perspective projection of the stored 3-D coordinates. This avoids opening a separate WebGL context for every visible model. The main atlas and expanded model explorer use Three.js with orbit controls.

## Data contract

The site reads three generated files from `public/data/`:

- `prompts.json`: one row per fixed prompt point, including the canonical 2-D and exploratory 3-D coordinates;
- `refusals.json`: genuine-refusal observations and the response-level fields exposed in the detail drawer;
- `metadata.json`: the source release, coverage counts and source/output hashes.

Rebuild these files with the repository's web-data builder. Do not edit them by hand. Coverage counts and the model-gallery headline are derived from the loaded data.

## Local review

```bash
cd interactive/web
npm ci
npm run build:pages
npm run preview:pages -- --host 127.0.0.1 --port 4173
```

Run `npm run lint` before publication. GitHub Pages uses the unlisted base path declared in `.github/workflows/publish-refusal-observatory.yml`.

## Brand assets

The funding page embeds the official partner marks from their public web sources and provides text alternatives. Confirm the legal funder name and final logo treatment before a public launch; the page currently follows the requested “Schmidt Foundation” wording.
