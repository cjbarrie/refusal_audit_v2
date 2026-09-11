# Model expansion execution checkpoint

Status reconciled at **2026-09-04 13:10 UTC**. This is an operational resume note,
not an analysis specification. Counts for live stages are snapshots and should
be recomputed from their append-only attempt ledgers before restarting anything.

> Hunyuan and GLM have now completed 12,480/12,480 responses each. Gemini's
> original run returned three empty responses. A resume under the original
> two-attempt authorization recovered two; the remaining Hindi response returned
> empty content on both permitted attempts and is a terminal provider-level
> missing response. Do not make a third attempt or manufacture response text.

## Completed generation stages

| Stage | Model | Complete | Expected | Provider cost | Next action |
|---|---|---:|---:|---:|---|
| 1 | Ministral 14B | 12,480 | 12,480 | $5.1360 | None; generation is complete and Luna v2.4 annotation is complete. |
| 2 | Nova Lite | 12,480 | 12,480 | $2.6370 | None; generation is complete and Luna v2.4 annotation is complete. |
| 3 | Llama 4 Scout | 12,480 | 12,480 | $2.2254 | None; generation is complete and Luna v2.4 annotation is complete. |
| 4 | Hunyuan A13B | 12,480 | 12,480 | $9.7516 | None; generation and Luna v2.4 annotation are complete. |
| 5 | GLM 4.7 Flash | 12,480 | 12,480 | $7.2131 | None; generation and Luna v2.4 annotation are complete. |
| 6 | Gemini 2.5 Flash Lite | 12,479 | 12,480 | $6.0455 | Luna v2.4 annotation is complete for all returned responses; preserve the one twice-empty Hindi request as provider-level missingness. |

The completed Luna v2.4 Batch 1 contains **37,440/37,440** valid annotations for
Ministral, Nova and Llama. Its recorded provider cost is **$17.7409** and its
result SHA-256 is
`3f14019c3aa6b5ec0890a69b61591a113b6fef81f750c5a6cc55f5cc04cfb80b`.

## Completed Kimi generation and annotation

Kimi K2.5 Stage 7 completed **12,480/12,480** responses at 00:11 UTC on
4 September 2026. The user authorized payload SHA-256
`b6eafbeb05583604c2c2cfbc712cd8a728416a9adebcd0e4e1ea357f3f7924a9`
under a $64.00 hard ceiling. The recorded provider cost was **$25.24821304**;
the results SHA-256 is
`4f71d1fa3728de116cd3d1e55c0ac9fe5d93bf500bb663a405dfdde31257ae8f`.
The run required 12,628 attempt records after an initial 32-worker start and a
16-worker resume. No response is missing. Do not restart this completed stage.

The Kimi Luna v2.4 annotation batch completed with **12,479/12,480** valid
annotations. It used 12,480 blinded, source-response-only requests under the
unchanged v2.4 codebook. Its provider payload SHA-256 is
`113e2a2d269e91814434ec25a2ee7765d8460f319ea81ac96751ee20ce55dfe9`.
The user authorized an $11.00 hard ceiling and the recorded provider cost was
**$4.97970716**. The result SHA-256 is
`a98cdf1ef6a8b97a911e866595b385862d82b5492b33d40f09cef11a02c0bd91`.
One Chinese response exhausted all three attempts because Luna classified it as
a substantive refusal without returning the required short evidence span. That
annotation is excluded rather than silently repaired or imputed.

Luna v2.4 annotation Batch 2 completed with **37,439/37,439** valid annotations.
The user authorized its 37,439-request payload SHA-256
`2a794718d80b41055cd5e151163ce221c8ddc79e2c657e5425fa3c8e954bbef0`
under a $35.00 hard ceiling at 16:54 UTC. The recorded provider cost was
**$17.47197028** and the result SHA-256 was
`2837700936afb5ccdae77080c5e43faf6abc60a290d3ed4153825258715e7832`.
It contains every returned Hunyuan, GLM and Gemini response, excluding only
Gemini's documented twice-empty provider response. That missing key remains in
the batch manifest under `source_missingness`; it was not converted into model
text or sent to Luna.

## Integration status

1. Treat the two documented missing expansion outcomes—one Gemini generation
   and one Kimi annotation—as missing, without imputation.
2. The seven models are now integrated through `pipeline/_expansion_input.R`
   and the root canonical estimators. The combined frame contains 224,544
   observed responses, 6,127 genuine refusals and 52,563 capability failures.
3. The full-bootstrap 18-model estimates are retained in `canon_021`.
   The promoted working release `canon_024` inherits those verified estimates,
   contains the accepted figure redesign, and passes 29/29 analytical checks
   plus 16/16 figure checks. Build a fresh release from a committed stable Git
   tree before the final archival paper freeze.

## Expanded analysis snapshots

A separately labelled 17-model snapshot was built after Batch 2 completed so
that the six fully annotated expansion models could be inspected without
waiting for Kimi. It contains 212,065 responses and lives under
the dated `archive/2026-09-04_expanded_analysis_snapshots/pipeline/expanded/`;
its figures are archived beside it. The scripts validate both Luna batch
manifests and keep genuine refusal and capability failure as separate outcomes.
This snapshot is retained for provenance and must not be confused with the
current 18-model output. The current analysis contains 224,544 labeled
responses, estimates and six 600-dpi PNG figures in that same dated archive.
They are retained as a development snapshot, not an active analysis surface.

## Apertus and other harder-access models

The prior Apertus 70B Public AI pilot remains a failed historical attempt:
0/200 completions, zero recorded provider cost. It must not be overwritten.

After the user accepted the gated repository terms, an authenticated catalogue
check on 2026-09-03 returned both Apertus v1.5 8B and 70B. A single 8B request
through the pinned Public AI route then succeeded with HTTP 200 in 0.63 seconds,
returning exactly `OK` (67 prompt tokens and two completion tokens). The record
is in
`annotations/model_expansion_v2/apertus_8b_access_smoke_v1/metadata.json`.

The new, versioned 8B pilot was frozen locally, using the same 40 prompt
meanings in all five languages (200 responses) and the canonical subject
generation settings. Its immutable provider
payload SHA-256 is
`f6ab8bdb46899f2a6973b6b8ea6cf62ef2ad8fd64c8efdd742bf8cc0d90ca5b2`.
At the published Public AI rate used for planning, its expected cost is $0.061,
its one-attempt maximum-output reservation is $0.201, its two-attempt reservation
is $0.402, and its hard ceiling was $0.50. The user authorized the exact payload
on 3 September 2026. Public AI returned no model response: 0/200 requests
completed after the authorized maximum of two attempts. There were 399
`PermissionDeniedError` records with the provider message `Your request was
blocked` and one explicit Cloudflare 1015 rate-limit record. Recorded provider
cost was $0.00. The result and attempt SHA-256 values are stored in the versioned
manifest and run summary. Do not resume this exhausted payload or count the
successful harmless smoke request as pilot evidence.

The runner exposed one implementation defect during this failure: it applied
the two-attempt allowance to non-transient permission failures as well as
transient errors. This did not exceed the authorized request-level maximum and
incurred no charge, but it created 199 unnecessary identical second attempts.
The shared Apertus runner was corrected after the run so only records explicitly
classified as transient can be retried. Historical ledgers were not altered.

This failure differs from the earlier repository-access failure: gated access
was working and an innocuous two-token request succeeded, but the canonical
political prompt workload was blocked. A further diagnostic would require a new
payload and authorization. Apertus remains outside the expansion panel unless a
route can return the unchanged canonical prompts.

GigaChat and Fanar remain access/setup work only:

- GigaChat: deferred by user decision on 3 September 2026 because legitimate
  native registration currently requires an access route the researcher does
  not have. Earlier route probes showed that the old Friendli
  endpoint was no longer present in the active workspace, and the API initially
  returned HTTP 403 because the team had no remaining credits. Attempts to
  create a replacement showed that Friendli's repository validator rejects both
  `ai-sage/GigaChat-20B-A3B-instruct-v1.5-bf16` and
  `ai-sage/GigaChat-20B-A3B-instruct-v1.5-int8` as invalid repositories. The
  original F32 repository had also failed to initialize. No deployment
  completed, no model response was returned, and no inference cost was
  recorded. Hugging Face reports no live Inference Provider for the original,
  v1.5 or int8 open-weight repositories. Friendli is therefore closed for this
  model family unless it explicitly adds support; do not try further weight
  variants there. Do not spend further time on GigaChat unless the user reopens
  access work; native Sber access and custom vLLM deployment remain possible
  future routes rather than current expansion stages.
- Fanar: request native Fanar API access while separately pricing a temporary
  endpoint for `QCRI/Fanar-2-27B-Instruct`.
- Neither model has an authorized scientific pilot or production run.

## Frozen comparability rule

Every new subject-model pilot and full run must retain the same prompt text,
one user message and no system message, temperature 1.0, maximum 5,000 output
tokens, disabled reasoning where supported, disabled provider fallback, and at
most two generation attempts. All five languages remain in the design even when
a model produces wrong-language or technically failed output; those failures
are outcomes rather than grounds for silently dropping a cell.
