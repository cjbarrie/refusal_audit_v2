# Local GGUF model expansion

This stage tests whether four otherwise difficult-to-access models can be run
reproducibly on the project machine. It is an operational screen, not an
analysis. No result from the one-meaning smoke can estimate refusal prevalence.

The completed pilots now feed the separate Torch full-corpus implementation in
`docs/HPC_LOCAL_GGUF_FULL_V1.md`. Cluster execution is deliberately kept out of
the pilot scripts so historical local records retain their original runtime.

The implementation is `scripts/local_gguf_expansion_smoke.py`; its pinned
roster is `config/model_rosters/local_gguf_expansion_v1.json`; generated records
live under `annotations/model_expansion_v4/local_gguf_smoke_v1/`. The larger
admission pilot is implemented by `scripts/local_gguf_expansion_pilot.py` and
writes only to `annotations/model_expansion_v4/local_gguf_pilot_v1/`.

## Why these models

| Model | Original developer | Jurisdiction | Contribution |
|---|---|---|---|
| Krutrim-2-Instruct | Ola Krutrim | India | New Indian developer; its cloud route was inaccessible |
| GigaChat3-10B-A1.8B | Sber AI / AI-Sage | Russia | New Russian developer and a current open GigaChat release |
| EuroLLM-22B-Instruct-2512 | UTTER / EuroLLM consortium | Europe | EU-funded model explicitly covering all study languages |
| Salamandra-7B-Instruct-2606 | Barcelona Supercomputing Center | Europe | Independent European creator with documented safety alignment |

The quantizer is not treated as the model developer. Original source model,
GGUF repository and quantizer are stored separately on every request.

## Frozen inputs and generation contract

The script takes the lexicographically first prompt ID from the existing frozen
40-meaning expansion pilot. It retrieves that exact meaning from each canonical
prompt file, yielding English, Chinese, Arabic, Russian and Hindi versions. Four
models by five languages gives 20 requests.

Every model uses Q8_0. Models run sequentially through the same local Ollama
installation with their native embedded chat template. The user-message text is
unchanged. Generation fixes temperature at 1.0, the requested maximum at 5,000
new tokens, context at 8,192 tokens and repetition penalty at 1.0. Other sampler
settings are runtime defaults and are recorded as such.

The local runtime incurs no inference-provider charge. It does require model
downloads and local compute. The stage records the Ollama version, platform and
complete `/api/show` response for each model. Request and response ledgers are
hashed, append-only/resumable, and isolated from existing provider runs.

## Commands

```bash
python3 scripts/local_gguf_expansion_smoke.py prepare
python3 scripts/local_gguf_expansion_smoke.py run
python3 scripts/local_gguf_expansion_smoke.py audit
```

A single downloaded model can be checked before the next download:

```bash
python3 scripts/local_gguf_expansion_smoke.py run --model krutrim-2-instruct-local-q8
```

## Decision rule

Successful generation is insufficient. Before a model advances, the 20
responses must be annotated with the unchanged Luna v2.4 codebook and inspected
for empty output, template leakage, reasoning leakage, wrong-language output and
capability failure. Passing models enter the existing 40-meaning by five-language
pilot. Acceptance is at the model-language-cell level.

Russia is absent from the prompt battery's home-region strata. Russian models
can enter overall, language and semantic-space analyses, but cannot support a
Russian home-versus-away estimand without a separately designed Russian-topic
sampling extension.

## Completed smoke: 9 September 2026

The frozen request ledger contains 20 rows and has SHA-256
`969d24132ca8d5ced360bf202a1e6b1f8000cc52c6e32e7ab232a9e91c0782fe`.
The selected meaning is
`issue_2026_hungarian_parliamentary_election_Q125627220__reg2`. The run used
Ollama 0.32.15 on an arm64 Apple M3 Max. The response ledger and machine-readable
audit are:

- `annotations/model_expansion_v4/local_gguf_smoke_v1/responses.jsonl`
- `annotations/model_expansion_v4/local_gguf_smoke_v1/audit.json`

The response ledger SHA-256 is
`dfdb7005e19eab62da01dddf62c3c3683055764e05b80a0da5e045910e9342c8`.
Fifteen of 20 requests returned text. The five failures all belong to one model
and arise before inference, so the manifest correctly remains `incomplete`.

| Model | en | zh | ar | ru | hi | Initial reading |
|---|---:|---:|---:|---:|---:|---|
| Krutrim-2-Instruct Q8 | 764 | 695 | 5,000 | 336 | 2,157 | Runs in all cells; Arabic hits the ceiling and mixes scripts |
| GigaChat3-10B-A1.8B Q8 | error | error | error | error | error | Weights load, but Ollama cannot parse the embedded chat template |
| EuroLLM-22B-Instruct Q8 | 791 | 1,224 | 393 | 546 | 800 | All five cells terminate normally and use the requested language |
| Salamandra-7B-Instruct Q8 | 774 | 2,164 | 4,248 | 786 | 929 | Runs in all cells; Hindi switches to English and Arabic is malformed |

Numbers are output-token counts, not quality scores. The “initial reading” is a
technical inspection used to design the next audit. It is not a substitute for
the v2.4 annotation codebook and cannot establish refusal prevalence.

### GigaChat runtime failure

The official GGUF identifies as the `deepseek2` architecture and its weights
load into memory. Ollama's embedded llama.cpp then stops while initializing the
GGUF chat template with `Unexpected token: -`, advises `--no-jinja` or a custom
template, and terminates the local server process. All five requests therefore
return HTTP 500 before seeing their prompt. This is a runtime incompatibility,
not evidence of refusal or weak language performance. The existing Ollama route
should not be retried unchanged.

The repair uses `scripts/gigachat_local_template_repair.py`. It starts the
`llama-server` binary bundled with Ollama on localhost port 11435 with Jinja
disabled. Because this llama.cpp build nevertheless validates some template at
startup, `chatml` is supplied only as a recognized startup template. The runner
never calls the chat endpoint and ChatML never formats an experimental prompt.
Instead, it calls raw `/completion` with the single-user sequence from the
official embedded GigaChat template:

```text
user<|role_sep|>
{canonical user prompt}<|message_sep|>

assistant<|role_sep|>
```

The model tokenizer supplies its configured beginning-of-sequence token. This
changes no user text or generation parameter and avoids silently substituting a
generic conversational format. The first diagnostic produced a coherent
658-token Russian response at approximately 19.3 tokens per second and stopped
at the model's end-of-sequence token.

The frozen repair payload has SHA-256
`fefa6286057361c0dafaeb399316da7f1638d41161b3ec34e19228e54176ef8f`.
All five repaired requests returned text and stopped at end-of-sequence. The
response ledger has SHA-256
`a6b17219fe9de0f769b836009964180d3cfbcb38bf8abb268c6c40a75dd48457`.

| Language | Output tokens | Technical result | Preliminary content reading |
|---|---:|---|---|
| English | 334 | EOS | Coherent knowledge-cutoff limitation |
| Chinese | 84 | EOS | Target language; asks for a more specific question |
| Arabic | 1,111 | EOS | Target-language substantive response |
| Russian | 145 | EOS | Coherent knowledge-cutoff limitation |
| Hindi | 3,976 | EOS | Target script but likely substantive degeneration |

These readings do not assign v2.4 outcomes. In particular, a knowledge-cutoff
limitation is not automatically a safety refusal, and target script is not
sufficient evidence of coherence.

### Advancement decision

EuroLLM advances to the larger admission pilot. Krutrim and Salamandra advance
only with close cell-level capability checks because the smoke reveals probable
wrong-language or capability-failure cells. The successful raw-completion repair
moves GigaChat past the access gate and into its own matched 40-meaning pilot;
its different local transport must remain explicit in all provenance. No paid
Luna or Sol annotation was performed in this local smoke.

## Frozen 40-meaning local pilot

The next stage crosses the exact 40 meanings in
`annotations/model_expansion_v1/openrouter_pilot_v1/pilot_prompt_index.csv`
with all five languages for Krutrim, EuroLLM and Salamandra. This produces 600
local requests. The prompt text and generation settings remain unchanged from
the smoke; execution remains one request and one model at a time. The runner is
append-only and resumes from successful request IDs after interruption.

```bash
python3 scripts/local_gguf_expansion_pilot.py prepare
python3 scripts/local_gguf_expansion_pilot.py run --model eurollm-22b-instruct-2512-local-q8
```

The selection intentionally spans earlier high-, moderate- and zero-refusal
cases plus diverse reference cases. It is enriched for diagnosis and therefore
cannot estimate population refusal or capability-failure prevalence. Its only
purpose is to decide which model-language cells merit full-corpus generation.

GigaChat uses the same 40 meanings and five languages but remains in the
separate `gigachat_raw_v1/` run directory because its transport is raw
llama.cpp completion rather than Ollama chat. `scripts/gigachat_local_pilot.py`
freezes and runs its 200 requests. `scripts/run_local_gguf_pilot_sequence.py`
then provides one resumable, unpaid sequence: GigaChat, Krutrim and Salamandra.
EuroLLM completed all 200 generation requests before this sequence began.

## Completed 40-meaning pilots: 10 September 2026

Generation is complete for the three models using Ollama chat. Their shared
ledger contains 600 unique requests and 600 non-empty responses: 40 prompt
meanings by five languages for each of Krutrim, EuroLLM and Salamandra. The
frozen logical payload has SHA-256
`783af5147111dda1bfbbb5bf80646ffbf21dedc4225d104474b4621ed0b827e7`;
the completed response ledger has SHA-256
`66e9c530992b5e297fae90198c61f26f827ba35807be9e91993d9152a4b4b8dc`.

The GigaChat raw-completion ledger covers the same 200 intended records. It has
199 non-empty responses: 40/40 in Chinese, Arabic, Russian and Hindi, and 39/40
in English. One English request, prompt ID
`issue_amos_yarkoni_Q2389273__bndA`, ended at the model's end-of-sequence token
after generating one token but no visible answer. A second independent attempt
reproduced the same one-token empty outcome. It is therefore retained as a
technical no-output result in the 200-record generation denominator rather than
retried until a different answer appears. A transient Chinese HTTP 500 was
successfully repaired on its second attempt. The GigaChat logical payload has
SHA-256
`c3e9b90ac70660a1551e1037670764529dbfad334b2ff3375bebab03b8b00f6e`.

These are deliberately enriched admission pilots, not probability samples from
the prompt corpus. Their raw refusal or failure proportions must not be reported
as prevalence estimates.

## Luna v2.4 annotation gate

`scripts/local_gguf_pilot_annotation.py` assembles the four pilots using the
append-only last-record rule. It writes an 800-row generation-outcome ledger so
the GigaChat no-output case remains explicit, and freezes 799 annotation
requests for the records that contain response text. Luna sees only the target
language, the unchanged target-language prompt, the English reference prompt
and the model response. It does not see the subject model, developer,
jurisdiction, pilot band or local transport. The system prompt and structured
output schema are byte-identical to the adopted v2.4 wall-to-wall annotation
contract. No translation is used.

The frozen 799-request provider payload has SHA-256
`0300d9c019467bd15ee2e92ed0f0721833ffa691806db3eac337d4de1fe2c94b`.
At the recorded Luna prices, its planning estimate is $0.5749 and its hard
provider-cost ceiling is $1.00. The user authorized this exact contract on 10
September 2026. The run cost $0.31395 and returned 798 schema-valid records
directly. One Arabic Krutrim response exhausted all three schema attempts: all
three Luna outputs agreed that the response was incoherent/garbled, affected by
encoding corruption and contained no substantive output, but also labelled an
apparent phrase as explicit refusal. That combination violates the frozen v2.4
rule that incoherent content cannot establish refusal. A deterministic local
consistency repair therefore changed only `substantive_refusal` to
`unassessable` and cleared its refusal-evidence span. All three raw provider
records remain intact. No fourth provider request was made. The resulting 799
labels have SHA-256
`877eae8551d6aa09e54bcacb3deb6dcdfd7446f0dcec7cf09da28ac5571998d1`.

After Luna annotation, admission remains a model-by-language decision. The
comparison will report genuine refusal, capability failure, wrong-language
output and mixed-language output separately. The single no-output record is a
generation failure, not a Luna-derived semantic classification.

### Provisional Luna admission signals

The strongest capability-failure signals are GigaChat Hindi (37/40), Krutrim
Arabic (36/40) and Hindi (21/40), and Salamandra Arabic (36/40), Hindi (40/40)
and Chinese (21/40). EuroLLM has no flagged capability failures in English,
Chinese or Arabic, one in Russian and eight in Hindi. GigaChat has at most three
in each non-Hindi language; Krutrim has none in English or Chinese; Salamandra
has one in English and one in Russian. These ratios describe the deliberately
enriched 40-meaning admission sample. They are useful for screening cells but
must not be presented as population rates.

Luna alone does not make the final admission decision. The next gate is a
blinded Sol v2.4 audit of every Luna-flagged refusal, capability failure or
wrong-language record plus probability-sampled apparently clean controls from
each model-language cell. The messages and schema must remain identical to the
Luna stage, and selection probabilities must be retained for design-weighted
agreement estimates.

That audit is implemented by `scripts/local_gguf_pilot_sol_audit.py`. The
frozen selection contains all 243 Luna-flagged responses and 171 apparently
clean controls. Within each model-language cell, the control sample contains
ten records or the entire clean remainder when fewer than ten exist. Control
ranking is the SHA-256 ordering of the fixed seed
`local-gguf-pilot-sol-audit-v1-20260910` and `audit_response_id`. Flagged cases
have inclusion probability one; each clean control records its cell-specific
sampling probability and inverse-probability weight. The weights reconstruct
the complete 799-response Luna-labelled population.

The resulting 414-request Sol payload has SHA-256
`af7291df3733812b21ef2fb907d6c403b4918cc95444cd97e33373439766a38d`.
It uses the same prompt, source-response-only messages and response schema as
Luna, with the model and provider changed to pinned OpenAI GPT-5.6 Sol. The
planning estimate is $2.8586 and the hard provider-cost ceiling is $5.50. The
user authorized the exact payload on 10 September 2026. Sol returned 414/414
schema-valid annotations at a provider-reported cost of $1.65823. The attempts
and results ledgers have SHA-256
`cfbed3c2426ff305f03b4ff9f38543e7973e04e6cf77afd885b6d0df1ebc2245`
and `aaaf10518f4a7601e9919a176855da526c15069ffdd372f541a1aa86fe505ff8`,
respectively.

Using the stored inverse-probability weights to reconstruct all 799
response-bearing pilot records, Luna and Sol agree on genuine refusal in 98.65%
of cases (weighted kappa 0.849). Treating Sol as a frontier reference, Luna's
refusal sensitivity is 84.7%, specificity 99.3%, precision 86.5% and F1 0.856.
They agree on capability failure in 92.14% (kappa 0.786; Luna sensitivity
92.6%, specificity 92.0%, precision 76.3%, F1 0.837). Wrong-language agreement
is 93.93%, but Luna's precision against Sol is only 33.8%: Luna's weighted rate
is 8.51% and Sol's is 3.32%. As in the earlier jurisdiction pilot, Luna's
wrong-language field is therefore a useful high-recall screen rather than the
final cell assessment.

Sol confirms severe capability problems in GigaChat Hindi (82.5%), Krutrim
Arabic (97.5%), Salamandra Arabic (85%), Salamandra Hindi (100%) and Salamandra
Chinese (25%). Its design-weighted capability estimates are at most 5% for all
EuroLLM cells; for GigaChat English, Chinese, Arabic and Russian; for Krutrim
English, Chinese and Hindi; and for Salamandra English. Krutrim Russian (15.75%)
and Salamandra Russian (8.75%) are intermediate. These remain admission-pilot
diagnostics, not full-corpus prevalence estimates.

No numerical admission cutoff was prespecified for this local pilot. Final
model-language inclusion must therefore be recorded as a transparent design
decision rather than presented as the result of a pre-existing statistical
test. A defensible conservative rule for the next expansion is: advance cells
with Sol-weighted capability failure at or below 5%; hold cells above 5% and at
or below 10% for targeted review; and do not advance cells above 10%. Under
that proposed rule, every EuroLLM cell advances; GigaChat advances except in
Hindi; Krutrim advances in English, Chinese and Hindi, with Russian and Arabic
held out; and Salamandra advances only in English, with Russian reviewed and
Arabic, Hindi and Chinese held out. This rule is a recommendation pending an
explicit project decision.
