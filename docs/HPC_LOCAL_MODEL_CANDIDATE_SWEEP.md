# Candidate local models for jurisdiction expansion

**Research memo, 11 September 2026.** This is a screening document, not an
authorization to download weights or generate responses. Repository revisions,
weight hashes, prompt wrappers and request ledgers must be frozen separately
before any pilot.

## Bottom line

The next local expansion should be deliberately small. The strongest immediate
additions are:

1. **YandexGPT-5-Lite-8B-Instruct** for Russia;
2. **Lucie-7B-Instruct-v1.1** for France;
3. **Teuken-7B-Instruct-v0.6** for the German-led OpenGPT-X consortium;
4. **Minerva-7B-Instruct-v1.0** for Italy; and
5. **Airavata** for the Indian academic ecosystem, if its gated weights can be
   accessed and the original checkpoint can be converted reproducibly.

This set adds four genuinely new foundation-model organizations and one new
institutional Indian post-training actor. It does more for the paper than
adding several variants of the same base model or several releases from a
developer already represented.

Two further models merit a small technical smoke test, but not immediate
admission: **Project Indus 1.1B IT** (Tech Mahindra, India) and **Poro 2 8B
Instruct** (Finnish consortium). Two others are useful only as within-developer
comparisons: **Falcon-H1-7B-Instruct** and **MiniCPM4.1-8B**. The former updates
an already represented UAE developer; the latter adds another Chinese creator
to a jurisdiction that is already comparatively well covered.

## What counts as a useful addition

A model enters the shortlist only if it is an instruction/chat model with
downloadable weights, can plausibly be served on one 48 GiB L40S (or with a
small, explicitly justified change), and has an identifiable developer whose
jurisdiction can be documented. General multilingual ability is not required:
all five language cells are generated and retained, and poor language fidelity
is measured as capability failure. However, the model must be capable of
receiving the same user message without a bespoke safety preamble or task
rewrite.

Creator diversity is more important than nominal model count. A local model
that is merely a regional fine-tune of Llama, Gemma or Qwen can still be
scientifically useful because post-training may alter refusal behaviour, but it
does not provide an independent foundation-model lineage. The model table
therefore records both the organization that performed the relevant training
and the upstream base.

The current Torch batch already covers Krutrim (India), GigaChat/Sber (Russia),
EuroLLM and Salamandra (Europe). Separate completed or running expansion work
covers Sarvam, Bielik and T-pro. The recommendations below are additions to
that roster, not replacements for it. See
[`HPC_LOCAL_GGUF_FULL_V1.md`](HPC_LOCAL_GGUF_FULL_V1.md) and
[`JURISDICTION_MODEL_EXPANSION_V1.md`](JURISDICTION_MODEL_EXPANSION_V1.md).

## Priority 1: pilot next

| Developer jurisdiction | Candidate | Developer and lineage | Local route | Why it earns a pilot | Main caveat |
|---|---|---|---|---|---|
| Russia | `yandex/YandexGPT-5-Lite-8B-instruct` | Yandex; 8B foundation model trained without third-party weights | Convert the official BF16 checkpoint to Q8 GGUF, or use the official Q4_K_M GGUF for the access smoke | Adds the largest missing Russian commercial developer and an independent foundation-model lineage | Custom Yandex licence requires a recorded legal check before publication use |
| France / EU | `OpenLLM-France/Lucie-7B-Instruct-v1.1` | OpenLLM-France/LINAGORA; instruction tuning of the from-scratch Lucie base | Official GGUF exists; create or pin a Q8 conversion from the official BF16 weights | Adds a French open-model consortium; Apache 2.0; distinct pretraining project | Post-training is described as light, so capability failure may be substantial |
| Germany-led EU consortium | `openGPT-X/Teuken-7B-instruct-v0.6` | Fraunhofer, Forschungszentrum Jülich, TU Dresden and DFKI; from-scratch 24-EU-language model | Convert the official BF16 checkpoint to GGUF, or serve BF16 with a pinned vLLM container | Strong sovereign-EU case and a new institutional developer group | v0.6 is CC BY-NC 4.0; publication and artifact distribution must remain non-commercial and attributed |
| Italy / EU | `sapienzanlp/Minerva-7B-instruct-v1.0` | Sapienza NLP with CINECA; from-scratch Italian-English base, SFT plus online DPO | Official GGUF repository; pin a high-quality quantization or reproduce Q8 from BF16 | Adds an Italian academic/government-funded model and explicitly documented safety post-training | Primarily Italian/English, so four study-language cells may fail |
| India | `ai4bharat/Airavata` | AI4Bharat; IndicInstruct tuning of Sarvam OpenHathi/Llama 2 | Accept gated terms, download official weights, then create a pinned GGUF conversion | Adds a major Indian academic lab and a Hindi-specific instruction-tuning process | Older 7B model, gated access, and shared upstream lineage with Sarvam/OpenHathi |

Evidence for these choices:

- Yandex describes the 8B instruct model as Russian/English, 32K-context and
  trained from its own pretraining checkpoint without third-party model
  weights. Yandex also publishes an official 4.92 GB Q4_K_M GGUF and permits
  research, non-commercial and commercial use under its custom terms
  ([model card](https://huggingface.co/yandex/YandexGPT-5-Lite-8B-instruct/blob/main/README.md?code=true),
  [official GGUF](https://huggingface.co/yandex/YandexGPT-5-Lite-8B-instruct-GGUF/tree/main),
  [licence commit](https://huggingface.co/yandex/YandexGPT-5-Lite-8B-instruct-GGUF/commit/55bbdef6266e5e51a3974737e96c283fc83bd471)).
- Lucie is an Apache-2.0 French-led model with an official llama.cpp-compatible
  GGUF. Its card says the instruction tuning is deliberately light, which is a
  reason to pilot rather than assume viability
  ([model card](https://huggingface.co/OpenLLM-France/Lucie-7B-Instruct-v1.1),
  [official GGUF](https://huggingface.co/OpenLLM-France/Lucie-7B-Instruct-v1.1-gguf)).
- Teuken v0.6 was pretrained on six trillion tokens across all 24 official EU
  languages by a German institutional consortium. The current checkpoint is
  explicitly for private, non-commercial, research and educational use
  ([model card](https://huggingface.co/openGPT-X/Teuken-7B-instruct-v0.6)).
  The older commercial v0.4 is Apache 2.0 but is not a like-for-like substitute
  for v0.6 ([v0.4 commercial card](https://huggingface.co/openGPT-X/Teuken-7B-instruct-commercial-v0.4)).
- Minerva is an Apache-2.0, from-scratch Italian-English model trained on about
  2.5T tokens by Sapienza NLP with CINECA support; its instruct checkpoint used
  SFT and online DPO and has an official GGUF repository
  ([model card](https://huggingface.co/sapienzanlp/Minerva-7B-instruct-v1.0),
  [GGUF repository](https://huggingface.co/sapienzanlp/Minerva-7B-instruct-v1.0-GGUF/tree/main)).
- Airavata is a gated Llama-2-licensed 7B Hindi/English model created by
  AI4Bharat by tuning OpenHathi on IndicInstruct. Its exact `<|user|>` and
  `<|assistant|>` wrapper is documented and must be reproduced literally
  ([official model card](https://huggingface.co/ai4bharat/Airavata)).

## Priority 2: smoke test, but do not count yet

| Candidate | Scientific value | Why it is not Priority 1 |
|---|---|---|
| `makers-lab/Indus-1.1B-IT` | Adds Tech Mahindra and a ground-up Hindi/dialect GPT-2-style model | At 1.1B it may mostly measure low capacity; the card is sparse and the custom licence needs review |
| `QCRI/Fanar-1-9B-Instruct` | The only clean new open-weight MENA developer found; QCRI/HBKU continued-pretrained Gemma 2 9B and applied substantial SFT/DPO | Reopened on 11 September for a separate local-weight study after the native content-filter outcomes were reclassified as deployed-system behavior |
| `LumiOpen/Llama-Poro-2-8B-Instruct` | Adds a Finnish university/industry/supercomputing consortium and a distinct Finnish post-training pipeline | It is based on Llama 3.1 and only Finnish/English are supported; Finnish is not one of the study languages |
| `tiiuae/Falcon-H1-7B-Instruct` | Modern TII model with explicit coverage of all five study languages and an official Q8 GGUF | TII/Falcon is already represented, so this is model evolution rather than a new jurisdictional developer |
| `openbmb/MiniCPM4.1-8B` | Efficient Chinese/English model from a distinct Chinese developer, with official GGUF | China already has substantially more creator coverage than Russia, India and MENA |
| `internlm/internlm3-8b-instruct` | Adds Shanghai AI Laboratory and has an official GGUF | Same prioritization issue as MiniCPM; the published GGUF metadata emphasizes English even though the family is Chinese-developed |

Project Indus is described as a ground-up 1.1B instruction-tuned model for
Hindi, Bhojpuri, Maithili and Dogri by Tech Mahindra's Makers Lab
([model card](https://huggingface.co/makers-lab/Indus-1.1B-IT)). Poro 2 is a
Finnish-English Llama 3.1 adaptation made by AMD Silo AI, the University of
Turku's TurkuNLP group and HPLT; a third-party GGUF includes Q8_0
([official model card](https://huggingface.co/LumiOpen/Llama-Poro-2-8B-Instruct),
[GGUF](https://huggingface.co/tensorblock/LumiOpen_Llama-Poro-2-8B-Instruct-GGUF)).

Falcon-H1 is particularly easy to run: TII publishes Q8_0 itself, and the card
lists Arabic, English, Hindi, Russian and Chinese among 18 supported languages
([official GGUF](https://huggingface.co/tiiuae/Falcon-H1-7B-Instruct-GGUF/blob/main/README.md)).
MiniCPM4.1 is Apache 2.0 and has an official llama.cpp-compatible GGUF
([official GGUF](https://huggingface.co/openbmb/MiniCPM4.1-8B-GGUF)); InternLM
also publishes an official 8B instruct GGUF
([official GGUF](https://huggingface.co/internlm/internlm3-8b-instruct-gguf)).

## Candidates to defer or exclude

- **BharatGen Param2-17B-A2.4B-Thinking** is scientifically interesting: it is
  a from-scratch 17B MoE with 2.4B active parameters and support for English,
  Hindi and 21 other Indian languages. It is nevertheless a thinking checkpoint
  with custom remote code, not a plain instruct model. More importantly, its
  research licence says public release, sharing, publishing or deployment of
  model outputs requires written approval. Do not run it for this paper without
  written permission and a separate runtime protocol
  ([model card](https://huggingface.co/bharatgenai/Param2-17B-A2.4B-Thinking),
  [licence](https://huggingface.co/bharatgenai/Param2-17B-A2.4B-Thinking/blob/main/LICENSE)).
- **SILMA-9B-Instruct** is a credible Arabic-specialized Gemma 2 model with
  readily available GGUFs, but the current legal entity describes itself as a
  Delaware LLC. It should not be counted as a MENA developer without stronger
  corporate-provenance evidence
  ([model card](https://huggingface.co/silma-ai/SILMA-9B-Instruct-v1.0),
  [terms](https://silma.ai/terms)).
- **ALLaM-7B-Instruct-preview** is a strong Saudi, from-scratch Arabic-English
  model, but ALLaM is already represented in the study. A newer local run would
  be a version-sensitivity exercise, not another independent developer
  ([official card](https://huggingface.co/humain-ai/ALLaM-7B-Instruct-preview/blob/main/README.md)).
- **Vikhr, Saiga and T-lite** are useful Russian adaptation projects, but they
  either reuse Meta/Qwen/Mistral/Yandex bases or repeat the already included
  T-Tech developer. They should not increase the headline count of independent
  Russian developers. A single one could later support a narrowly framed
  base-versus-local-post-training analysis.
- **Meltemi-7B-Instruct** (Greece), **Poro-34B-chat** (Finland), and other
  language-specific European models are defensible, but Europe already has the
  richest local shortlist. Adding all of them now would worsen the regional
  imbalance the expansion is meant to address.
- Base-only checkpoints, embedding models, translation models, reward models,
  multimodal-only checkpoints and unofficial merges are out of scope. A model
  must answer the canonical user message as a general assistant.

## What the sweep says about MENA coverage

There is no honest way to obtain a large new MENA creator count simply by
searching deeper. The credible open-weight set is concentrated in TII/Falcon
(UAE), G42/MBZUAI/Jais (UAE), SDAIA/HUMAIN/ALLaM (Saudi Arabia), and QCRI/Fanar
(Qatar). The first three are already represented in the project. The clean new
creator is therefore QCRI, via the published Fanar-1-9B-Instruct weights.

QCRI identifies this checkpoint as an Apache-2.0 Arabic-English model developed
at HBKU and sponsored by Qatar's communications ministry. It continued-pretrained
Gemma 2 9B on one trillion Arabic/English/code tokens and then used 4.5 million
SFT examples and 250,000 DPO pairs
([official model card](https://huggingface.co/QCRI/Fanar-1-9B-Instruct)).
That makes it scientifically credible. The earlier decision to stop Fanar work
was explicitly reversed on 11 September 2026 for the limited experiments in
`FANAR_EXPERIMENTS_V1.md`.

Running Fanar locally answers a different question from the retained native
Fanar-C-2 API pilot. It removes the provider-side content filter and fixes the
checkpoint, but it also changes the model from C-2 27B to Fanar-1 9B. The local
result can expand the Qatari developer panel; it cannot diagnose or replace the
API model's behaviour.

SILMA and Arabic adaptations developed outside the region may be useful Arabic
language comparators, but language specialization is not developer
jurisdiction. They should not be placed in the MENA jurisdiction facet merely
because they answer well in Arabic.

## Proposed admission protocol

Do not add these candidates to the running 49,920-response array. Finish and
audit that immutable batch first. Then create `local_gguf_hpc_v2` as a separate
roster and ledger.

For each candidate:

1. **Provenance and licence gate.** Record developer, upstream base, licence,
   model-card URL, immutable repository revision, tokenizer/chat-template hash,
   weight hash and quantization provenance. If we make the GGUF, record the
   source weight hashes, exact llama.cpp commit and conversion command.
2. **Five-request access/template smoke.** Use one matched prompt meaning in all
   five languages. The source prompt must appear exactly once. Reject template
   echo, empty output, hidden system content or a model that cannot disable a
   mandatory reasoning trace.
3. **One-hundred-response mechanical benchmark.** Use the existing 20 meanings
   per language design to measure startup, memory, throughput, truncation,
   output loops and wrapper leakage. This is not an estimate of refusal
   prevalence.
4. **Two-hundred-response behavioural pilot.** Use the same frozen 40 meanings
   crossed with five languages. Annotate every returned response with Luna
   v2.4, then send every flagged response plus probability-sampled clean
   controls to Sol, exactly as in the completed local-model benchmark audit.
5. **Cell-specific admission.** Generate the full five-language corpus for a
   model that passes the operational gate, but predeclare which refusal
   contrasts will be point-estimable and which will be reported as bounds when
   unassessable output is material. Do not silently drop weak language cells.

The canonical generation settings remain temperature 1.0, maximum 5,000 new
tokens, no added system message, and at most two transient-error attempts. A
model with a shorter hard context/output limit must be recorded as a
provider/model constraint, as was done for Sarvam. Any model-specific flag used
to suppress reasoning must be verified not to alter the user prompt.

## Compute and storage implications

All Priority 1 models are 7--9B and should fit comfortably on one 48 GiB L40S
in BF16 or high-quality GGUF form. Based on the observed local benchmark, a
full 12,480-response model is likely to consume roughly 12--35 L40S GPU-hours;
response length, not parameter count alone, drives the range. Ten deterministic
shards can reduce elapsed time, but they do not reduce allocated GPU-hours.
These are planning ranges only: the 100-response benchmark must determine the
actual shard wall-time and safe parallel-slot count.

Prefer Q8_0 when a trustworthy conversion fits. If only a community GGUF is
available, use it for the five-request smoke, then reproduce the production Q8
from the official source checkpoint. This avoids treating an unknown community
conversion as part of the model's behavioural identity. A 7--9B Q8 file is
usually about 8--10 GB, so the complete Priority 1 weight set is modest relative
to the four existing 55 GB of local weights.

## Recommended sequence

The most informative next batch is **Yandex + Lucie + Teuken + Minerva**. It
raises Russia to three distinct developers and broadens Europe beyond Mistral,
BSC, EuroLLM and SpeakLeash without changing the MENA or Indian protocols while
their current runs settle.

After those four pilots:

- run the separately frozen **local Fanar-1 9B** pilot described in
  `FANAR_EXPERIMENTS_V1.md`;
- run **Airavata** if gated access is granted and its original weights can be
  reproducibly converted;
- use **Project Indus** only if the pilot shows that a 1.1B model yields enough
  assessable output for refusal measurement; and
- add **Falcon-H1** only as an explicitly labelled within-TII update.

This order improves jurisdictional coverage while keeping the unit of evidence
clear: a developer/checkpoint is a subject system, not an interchangeable vote
for its jurisdiction.

## Sources and search scope

The sweep used current official model cards, official organization pages and
licence files where available, plus GGUF repositories solely to establish
llama.cpp feasibility. Search covered Russia; France, Germany, Italy, Finland,
Greece and the broader EU; India; Saudi Arabia, Qatar and the UAE; and a smaller
China backfill. Information was checked on 11 September 2026. Hugging Face
cards and licences are mutable, so the eventual pilot manifest must pin exact
revisions rather than relying on `main`.
