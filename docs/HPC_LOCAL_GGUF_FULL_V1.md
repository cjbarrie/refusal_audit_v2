# Torch full-corpus run for the local GGUF models

This is the reproducible cluster implementation for Krutrim-2-Instruct,
GigaChat3-10B-A1.8B, EuroLLM-22B-Instruct-2512 and
Salamandra-7B-Instruct-2606. These four models passed the access and template
stage on the project machine. The cluster changes the hardware and serving
process; it does not change the 2,496 prompt meanings, five prompt translations
or generation settings.

The Slurm account is `torch_pr_309_social_sciences`, confirmed by
`my_slurm_accounts` on 10 September 2026. Jobs request one L40S GPU each. They
must never run on a login node. Torch supplies `apptainer` on its base system
path; the jobs verify the executable directly and do not try to load a
nonexistent Lmod module.

## What is frozen

`config/model_rosters/local_gguf_hpc_v1.json` pins each GGUF repository,
revision and Q8_0 filename. It also fixes temperature at 1.0, maximum output at
5,000 tokens, repetition penalty at 1.0 and context at 8,192 tokens per parallel
slot. The server has four slots and therefore receives a total context setting
of 32,768. All calls use llama.cpp's raw completion endpoint so the wrapper is
explicit rather than silently selected by a server:

- EuroLLM and Salamandra use the exact single-user ChatML branch recorded by
  Ollama in the completed pilot.
- Krutrim uses its recorded `<|user|>` / `<|assistant|>` single-user branch.
- GigaChat uses the official `role_sep` / `message_sep` sequence already tested
  by `scripts/gigachat_local_template_repair.py`.

The original user-message text appears exactly once and is never translated or
rewritten at this stage. Using raw completion also prevents a future container
update from choosing a different chat template. The fixed server image tag is
`ghcr.io/ggml-org/llama.cpp:server-cuda-b10335`; the bootstrap job records the
actual SIF SHA-256, and every generation task records that SHA alongside the
downloaded weight SHA. The pinned image stores its dynamically linked llama.cpp
libraries under `/app`; the runner explicitly adds `/app` while retaining
Apptainer's injected NVIDIA-library directory. This avoids relying on Docker's
entrypoint environment, which Apptainer does not reproduce automatically.

The intended frame is 49,920 generations: four models × five languages × 2,496
prompt meanings. We retain and annotate all language cells, including cells
expected to fail. Capability failure is an outcome, not a pre-annotation
filter. The v2.4 coder assigns refusal, language fidelity and output quality
independently: a wrong-language or degraded output can also contain a genuine
refusal. A wholly incoherent output leaves refusal unassessable rather than
automatically making it a non-refusal. Any later decision that a cell is not
reliably estimable applies only to a stated refusal contrast; it does not remove
the observations from the response ledger or capability-failure analysis.

## Execution design

`hpc/prepare_local_gguf_full.py prepare` creates an immutable request ledger and
a 40-row task map. Every model × language cell has two deterministic shards.
The full Slurm array allows at most eight simultaneous GPUs. Within each GPU,
llama.cpp continuously batches four requests. Each shard writes its own
append-only attempt and result ledgers, so re-submitting the same task resumes
instead of overwriting completed records.

HTTP 408, 429 and 5xx responses and transport errors may be attempted once
more. Deterministic errors and successful empty outputs are retained after the
first response. No request may exceed two attempts across restarts.

Before the full array, a benchmark sends 100 frozen requests per model: 20 in
each language. It tests startup, GPU memory, output integrity, batching and
throughput. Benchmark responses are operational checks and do not enter the
analysis. Inspect all four benchmark task summaries and server logs before
submitting the full array.

## First-time commands

From the Mac, copy the working project to Torch scratch. The data-transfer node
is preferable for a large transfer:

```bash
LOCAL_REPO=/path/to/refusal_audit_v2
rsync -az --exclude '.git' --exclude 'annotations/model_expansion_v4/local_gguf_full_hpc_v1/shards' \
  "${LOCAL_REPO}/" \
  cb5691@dtn.torch.hpc.nyu.edu:/scratch/cb5691/refusal_audit_v2/
```

On Torch:

```bash
cd /scratch/cb5691/refusal_audit_v2
mkdir -p hpc/logs
python hpc/prepare_local_gguf_full.py prepare
python -m unittest hpc/tests/test_local_gguf_hpc.py

BOOTSTRAP_JOB=$(sbatch --parsable hpc/slurm/00_bootstrap.sbatch)
DOWNLOAD_JOB=$(sbatch --parsable --dependency=afterok:${BOOTSTRAP_JOB} hpc/slurm/01_download_models.sbatch)
BENCHMARK_JOB=$(sbatch --parsable --dependency=afterok:${DOWNLOAD_JOB} hpc/slurm/02_benchmark.sbatch)
echo "bootstrap=${BOOTSTRAP_JOB} download=${DOWNLOAD_JOB} benchmark=${BENCHMARK_JOB}"
```

Watch without repeatedly opening output files:

```bash
squeue -u cb5691
sacct -j "${BENCHMARK_JOB}" --format=JobID,State,Elapsed,MaxRSS,ReqTRES%60
```

After all four benchmark tasks finish, inspect
`annotations/model_expansion_v4/local_gguf_full_hpc_v1/benchmark/` and the four
`hpc/logs/benchmark_*` files. Generate the compact mechanical summary with:

```bash
python hpc/audit_benchmark.py
```

Do not submit the production array until startup, memory, output integrity and
throughput look reasonable. A mechanical pass is not itself authorization to
launch production. Then:

```bash
FULL_JOB=$(sbatch --parsable hpc/slurm/03_generate_full.sbatch)
echo "full=${FULL_JOB}"
```

If tasks are interrupted, resubmit the same array. Completed request IDs are
skipped and attempt counts are read from the append-only ledgers. Once all
tasks finish:

```bash
python hpc/prepare_local_gguf_full.py audit
```

The audit expects 49,920 result records and writes one deterministic merged
`responses.jsonl` only when every request has a terminal record. It reports
non-empty output, empty output and runtime/transport failure separately. It
does not assign refusal or capability labels; those come from the unchanged
v2.4 annotation pipeline after the response ledger is copied back.

## Completed benchmark: 10–11 September 2026

All four 100-response tasks completed with exit code `0:0`. The benchmark
returned 400/400 non-empty responses with no request, transport or runtime
errors and no chat-template tokens in response text. Wall time was 11.2 minutes
for Krutrim, 5.5 for GigaChat, 14.9 for EuroLLM and 16.2 for Salamandra. Peak
resident memory was approximately 23.2, 17.2, 32.0 and 18.6 GiB,
respectively—comfortably below the L40S allocation.

Mechanical success does not imply a competent language cell. Maximum-length
responses recurred in the cells already identified by the independent pilot:
Krutrim Arabic 6/20 and Hindi 2/20; GigaChat Arabic 1/20 and Hindi 12/20; and
Salamandra Arabic 5/20 and Hindi 6/20. EuroLLM had no 5,000-token response in
any language. Deterministic script diagnostics also found isolated wrong-script
responses for Krutrim Chinese and Russian, and frequent wrong-script or corrupt
Hindi from Salamandra. These checks agree with the earlier Luna/Sol audit; they
are diagnostics rather than replacement semantic labels.

After benchmark review and explicit approval, production array job `17368291`
was submitted on 11 September 2026. It completed on 12 September. The
deterministic audit recovered all 49,920 terminal records and no missing keys:
49,879 successful non-empty responses, 28 explicit empty responses and 13
HTTP/runtime failures. The merged response ledger has SHA-256
`878beee4360fa7304296818e0ee72dfad964d64d0e63e9f6888f2ff883285fe6`.
The design therefore retains all 20 model-language cells and the complete
generation denominator. There was no pre-generation or pre-annotation
refusal-admission filter.

The benchmark was then annotated in full with the unchanged Luna v2.4
source-response-only codebook. The frozen payload contained exactly 20
responses in each of the 20 model-language cells; its SHA-256 was
`52905505d348367bb6cee09dcda387ba86ec1617eef2144fda3e5f02fe5e3904`.
All 400 requests returned valid schemas on 11 September 2026 and cost $0.166912
against a $0.50 ceiling. Luna identified three genuine refusals, 108 capability
failures, one response carrying both labels, and one response for which refusal
was unassessable. These were screening results rather than final benchmark
truth.

The Sol follow-up audited all 110 Luna-flagged records—including all 108
capability failures—and 161 deterministically probability-sampled clean
controls. Inverse-probability weights reconstruct the 400-response benchmark.
Sol received byte-identical v2.4 messages and schema and could not see Luna's
labels or selection stratum. The frozen payload SHA-256 was
`febca4abfb1db087e2fb9e01b648b5aab00a99bb2dca8dbb7588aaec8de444af`.
All 271 requests returned valid schemas on 11 September and cost $1.144755
against a $3.50 ceiling.

Treating Sol as the frontier reference, design-weighted Luna agreement was
99.75% for genuine refusal and 93.5% for capability failure. Luna found both
Sol refusals and added one false positive. For capability failure it found all
82 Sol-positive records but added 26 false positives. Wrong-language coding was
the principal problem: Luna estimated 10.5% against Sol's 2.5%.

Sol retained two genuine refusals: one GigaChat Arabic response and one Krutrim
Arabic response. The Krutrim response was also a capability failure, directly
confirming that the outcomes overlap. Sol marked 13/400 refusal states
unassessable, concentrated in GigaChat Hindi (7/20), Salamandra Hindi (5/20)
and Salamandra Arabic (1/20). On the benchmark, the unconditional refusal
bounds were therefore 0–35%, 0–25% and 0–5% for those cells. These are gate
diagnostics based on 20 responses per cell, not paper estimates.

## Full-corpus semantic annotation

`scripts/local_gguf_hpc_full_annotation.py` applies the unchanged Luna v2.4
measurement contract to a census of the 49,879 response-bearing records. It
does not send the 28 empty responses or 13 HTTP/runtime failures to a semantic
text classifier because those records contain no response to judge. Instead,
all 49,920 generation outcomes are preserved in
`generation_outcomes.parquet`, with the 41 unusable records retained as
separate technical outcomes. They are not recoded as engagement, refusal or
capability failure.

For each usable record, Luna receives only four pieces of source material: the
target language, the English reference prompt, the target-language prompt and
the original model response. It does not receive the subject model, developer,
jurisdiction, topic metadata, selection status or any earlier annotation. The
request uses the adopted `response-validity-v2.4` prompt and JSON schema,
`openai/gpt-5.6-luna` pinned to OpenAI, temperature 0, a 500-token maximum,
reasoning disabled and provider fallbacks disabled. Refusal, capability
failure and language fidelity remain separate fields, so a degraded or
wrong-language response can still contain a refusal.

The local freeze and price calculation are:

```bash
python scripts/local_gguf_hpc_full_annotation.py prepare
python scripts/local_gguf_hpc_full_annotation.py cost
```

As frozen on 12 September 2026, the payload contains 49,879 requests and has
SHA-256 `a7a09867f9303f2a41e718b539a11b4f241d2b94c54d4968cd63450001e193e7`.
The input estimate is 122,265,048 tokens. At the then-current pinned OpenAI
route price of $0.20 per million input tokens and $1.20 per million output
tokens, the planning estimate is $36.42. Previous Luna runs project $23.44 at
their observed cost per response. The guarded hard ceiling is $54.75. These
local preparation steps made no provider call. The user explicitly authorized
this exact 49,879-request payload, pinned route and $54.75 ceiling on 12
September 2026 at 16:43 UTC. The authorization was recorded in the immutable
manifest before the first provider request. The resumable 32-worker run then
started under `caffeinate` and completed at 17:37 UTC. It returned 49,867 valid
annotations and 12 exhausted consistency conflicts, for a provider-reported
cost of $20.177800. Schema success was 99.976%, above the 99.5% operational
gate. The attempt-ledger SHA-256 is
`66a3823d73ba95d2a5113e1f246acb853f706484e923cf8f44faf124cd3cd29a`;
the 49,867-record result-ledger SHA-256 is
`9d72c598439717889587f7d43024215dfe8d4e00d62e2a88bc427a53aed4794a`.

All 12 unresolved cases exhausted three attempts on the same validator rule:
the draft simultaneously called the output incoherent or unassessable and
assigned explicit or implicit substantive refusal. This is a logical schema
conflict, not an API or transport failure. The cases are concentrated in
GigaChat Hindi (4), Krutrim Arabic (1), Salamandra Arabic (6) and Salamandra
Hindi (1).

The repair is a separate immutable stage implemented by
`scripts/local_gguf_hpc_full_annotation_repair.py`. It uses the same adaptive
repair wording previously validated on the 129 exhausted original-panel cases:
Luna must re-read the full response and decide whether it coherently
communicates withholding or is genuinely unassessable. Wrong language remains
independent. The repair does not change the v2.4 codebook, fields, enum values
or JSON schema, and it preserves all three invalid drafts.

The frozen repair contains 12 requests and permits at most two attempts per
case. Its initial payload SHA-256 is
`0002de774fa94e01ba81c30d53a52b70d626f65cf261b91f49e63e99a3683d51`;
the adaptive protocol SHA-256 is
`430e7f18b75708667f1ae8a04324518c9f2d713dbdee9b7f21b8fe817a684c32`.
The maximum two-attempt planning estimate was $0.019369, the maximum-token
reserve was $0.028009 and the guarded hard ceiling was $0.25. Preparation and
costing made no provider call. The user authorized both hashes and the ceiling
on 12 September at 19:13 UTC. All 12 requests returned valid annotations on
their first repair attempt, costing $0.006437. No adaptive second attempt or
Sol contingency was needed. The repair attempt SHA-256 is
`8c635452140ee40edda55bc8f2ba1d42738cb75f2d6a0ef3bb4bfdb37c76cec1`;
the repair result SHA-256 is
`d57a873db008d7eb000e72d49ecadfe5f67cbee0abfad49381511971b2d430c8`.

Eleven repairs resolved to `substantive_refusal=unassessable` with
`output_quality=incoherent_garbled`. One Krutrim Arabic response was judged
partly coherent enough to establish an explicit refusal; it was also a
wrong-language repetition-loop capability failure. This illustrates why the
repair re-judged the response rather than deterministically changing every
refusal field to `unassessable`.

The final lossless assembly contains all 49,879 response-bearing records:
49,867 labels from the main run and 12 from repair. It has 49,879 unique
`(prompt_id, prompt_language, subject_model)` keys and explicit row-level label
provenance. The assembled-label SHA-256 is
`f6f1c3afe59bc48db191cd3d423d491a63ab5eda82d0c10aee813992931f587d`.
It contains 381 derived genuine-refusal labels and 13,630 derived capability
failures, including 65 responses carrying both outcomes. These are unadjusted
corpus counts, not standardized or causal estimates.

## Probability-based Sol audit

The full Luna census is followed by a focused audit with
`scripts/local_gguf_hpc_full_sol_audit.py`. Sol is used as an independent
frontier-model reference, not as human ground truth and not as a replacement
for the Luna labels. The design includes every Luna-coded genuine refusal
(381) and every remaining response for which Luna could not determine refusal
status (271). It then draws deterministic simple random samples, separately
within each model-language cell, of up to 20 assessable capability failures
and up to 20 apparently clean responses. This adds 298 capability-failure
cases and 385 clean controls, for 1,335 reviews in total.

Each sampled record stores its inclusion probability and inverse-probability
weight. The weights sum to the full 49,879-response population, allowing the
audit to estimate full-population Luna-Sol agreement and outcome differences
without pretending that the deliberately enriched review set is a simple
random sample. Census strata have weight one. Sol receives the exact messages
and JSON schema used for Luna and cannot see Luna's labels, model identity,
selection stratum or weight.

The frozen Sol payload has SHA-256
`5292840f2227103fb4cd575c3a2b1b1b687c8035e2a0dad4fec5da58759f2be2`.
At the OpenRouter price verified on 12 September 2026—$2 per million input
tokens and $10 per million output tokens—the planning estimate is $9.11 and
the single-attempt maximum-token reserve is $13.11. The proposed guarded hard
ceiling is $16.50. Preparation and costing made no provider request. The user
authorized this exact payload and ceiling on 12 September 2026 at 19:36 UTC.
The 24-worker run returned 1,328 valid labels and seven exhausted consistency
conflicts for $5.240928. The attempt-ledger SHA-256 is
`4917af713f5aa9615e92460ceafb649a029756fe9690d9fa25e2d4f64ad9a5dd`;
the valid result-ledger SHA-256 is
`a6f7e412a55aafcb770b91ea14caa87958e310ad3e19568ef4c7c7a4c69a712d`.

All seven unresolved records failed the same logical check on all three base
attempts: the draft called the response incoherent or unassessable while also
claiming that it established an explicit or implicit refusal. They are not
dropped or automatically recoded. A separate adaptive repair has been frozen
with initial payload SHA-256
`59f9ac6d3d96366c4d474447abfc5695f0d93b5f400e1bb4d3c02a3d7f05daae`
and protocol SHA-256
`a1b36605680a981dbf6146a3d629413ccd146f7aad5bc4d56a2c34b6ed0b3e3e`.
It permits at most two Sol attempts per case, has a maximum-two-attempt
planning cost of $0.094 and a proposed hard ceiling of $0.25. At the freeze
stage it was not yet authorized or run; design-weighted scoring remained
blocked so that no enriched audit case could be silently omitted.

The user subsequently authorized that exact repair payload, protocol and
ceiling on 12 September 2026 at 19:48 UTC. All seven cases returned valid
labels in the first adaptive round for $0.026484. The repair attempt-ledger
SHA-256 is
`d5f31bbb4264ce8039f28dc2f7c61c02de00cda572f785569e8d9498a7234d79`;
the repair result-ledger SHA-256 is
`93a4dd64db91aba24430630282525e541d920c113950623ba9b776764dd82af6`.
The lossless 1,335-record assembly has SHA-256
`0cf12fb0a94bece20d220ad33b1a6c6ecf7e9e7db5b09d6d9e2b24c7405be12f`.
Main and repair calls together cost $5.267412.

Treating Sol as a frontier machine reference, the design-weighted genuine
refusal rate is 0.651%, compared with Luna's 0.764%. Luna-Sol agreement on the
derived binary refusal outcome is 99.87% (kappa 0.909), sensitivity is 98.78%,
specificity 99.88% and positive predictive value 84.25%. In substantive
terms, Luna detected nearly all Sol refusals but classified 60 of its 381
positive cases as refusals that Sol did not confirm. The weighted estimate of
Sol-positive refusals among Luna-negative responses is approximately four
cases in the 49,879-response population.

The capability results are less stable across annotators. Sol estimates a
21.49% capability-failure rate, compared with Luna's 27.33%; agreement is
93.43% (kappa 0.823). The largest measurement discrepancy is wrong-language
output: 3.52% under Sol versus 10.44% under Luna. This gap is concentrated in
Hindi and in specific local model-language cells. Therefore the Torch models'
main refusal estimates may proceed with the Sol audit adjustment and its
design uncertainty, but Luna-only wrong-language and capability-failure counts
must not be treated as settled paper estimates.

The local preparation commands are:

```bash
python scripts/local_gguf_hpc_full_sol_audit.py prepare
python scripts/local_gguf_hpc_full_sol_audit.py cost
```

After exact authorization, the guarded commands are:

```bash
python scripts/local_gguf_hpc_full_sol_audit.py authorize \
  --payload-sha <authorized_sha256> \
  --cost-ceiling <authorized_ceiling> \
  --confirm-user-authorization
python scripts/local_gguf_hpc_full_sol_audit.py run \
  --workers 24 \
  --cost-ceiling <authorized_ceiling> \
  --authorize-paid-run
python scripts/local_gguf_hpc_full_sol_audit.py score
```

After authorization, the guarded commands are:

```bash
python scripts/local_gguf_hpc_full_annotation.py authorize \
  --payload-sha <authorized_sha256> \
  --cost-ceiling <authorized_ceiling> \
  --confirm-user-authorization
python scripts/local_gguf_hpc_full_annotation.py run \
  --workers 32 \
  --cost-ceiling <authorized_ceiling> \
  --authorize-paid-run
python scripts/local_gguf_hpc_full_annotation.py summarize
```

The guarded repair commands are:

```bash
python scripts/local_gguf_hpc_full_annotation_repair.py prepare
python scripts/local_gguf_hpc_full_annotation_repair.py cost
python scripts/local_gguf_hpc_full_annotation_repair.py authorize \
  --payload-sha <authorized_sha256> \
  --protocol-sha <authorized_protocol_sha256> \
  --cost-ceiling <authorized_ceiling> \
  --confirm-user-authorization
python scripts/local_gguf_hpc_full_annotation_repair.py run \
  --workers 12 \
  --cost-ceiling <authorized_ceiling> \
  --authorize-paid-run
python scripts/local_gguf_hpc_full_annotation_repair.py assemble
```

The runner is append-only and resumable. The summary refuses to assemble until
all 49,879 records have schema-valid terminal annotations. The full analysis
will report definite refusal, capability failure, their overlap and
refusal-unassessable output separately. Where unassessability is material, the
unconditional refusal result will be an identified lower/upper bound. A
competence-conditioned refusal rate remains a secondary,
selection-conditioned sensitivity rather than a silent replacement for the
unconditional outcome.

## Outputs

Generated state lives in the gitignored directory
`annotations/model_expansion_v4/local_gguf_full_hpc_v1/`:

- `requests.jsonl`: frozen logical payload, including explicit raw wrappers;
- `manifest.json`: input hashes, request hash, settings and expected counts;
- `task_map.json`: exact Slurm task-to-cell/shard assignment;
- `benchmark/task_*/`: benchmark attempts, responses, server log and runtime;
- `shards/task_*/`: production attempts, responses, server log and runtime;
- `audit.json`: coverage audit; and
- `responses.jsonl`: complete merged generation ledger, created only at full
  coverage.

The separate gitignored annotation directory is
`annotations/model_expansion_v4/local_gguf_full_hpc_luna_v2_4_v1/`. Its frozen
inputs are `generation_outcomes.parquet`, `response_index.parquet`,
`provider_requests.jsonl`, `prompt.txt`, `response_schema.json`, `manifest.json`
and `cost_estimate.json`. After a complete paid run it also contains append-only
attempts, schema-valid results, the run summary, assembled labels and cell-level
outcome tables.

Weights, the Apptainer image, Hugging Face cache and their lock records live
under `/scratch/cb5691/refusal_audit_hpc/`, not in Git. Secrets are not required
for these public repositories and must not be placed in the Slurm files.
