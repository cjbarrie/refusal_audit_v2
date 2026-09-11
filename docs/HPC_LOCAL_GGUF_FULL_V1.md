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

At the observed request latencies, generating all 20 cells is projected to use
about 93 L40S GPU-hours. With eight simultaneous tasks, expected elapsed time is
roughly 12–16 hours after scheduling. Every individual shard projects below six
hours, leaving a substantial margin under the 24-hour task limit. After
benchmark review and explicit approval, production array job `17368291` was
submitted on 11 September 2026. It is resumable and was still running at the
time of this update, so no changing partial count is treated as a completed
result. The design fixes the scope at all 20 model-language cells. There is no
pre-generation or pre-annotation refusal-admission filter.

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

The production recommendation is to generate all 49,920 responses. All 20
cells remain part of the system-behaviour population and will receive the same
joint v2.4 annotation. The full analysis will report definite refusal,
capability failure, their overlap and refusal-unassessable output separately.
Where unassessability is material, the unconditional refusal result will be an
identified lower/upper bound. A competence-conditioned refusal rate will be a
secondary, explicitly selection-conditioned sensitivity rather than a silent
replacement for the unconditional outcome.

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

Weights, the Apptainer image, Hugging Face cache and their lock records live
under `/scratch/cb5691/refusal_audit_hpc/`, not in Git. Secrets are not required
for these public repositories and must not be placed in the Slurm files.
