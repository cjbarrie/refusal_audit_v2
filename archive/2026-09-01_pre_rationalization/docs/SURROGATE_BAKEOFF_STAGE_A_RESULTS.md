# Stage A GPT-5.6 Luna surrogate bake-off results

## Scope and provenance

This is a prompt-configuration development experiment, not a population
validation result. It compares five frozen annotation configurations on the
same 84 frozen, human-coded evaluation responses. The 84 rows were grouped by
`prompt_id` before splitting, so no prompt family crosses from the 216-row
development pool into evaluation. The evaluation set deliberately contains
rare classes and is not population weighted.

The user authorized the exact 420-request logical payload with SHA-256
`42eb65c4da98631a00f4479a5810ff8b4da044105845631679e021d9e03caafb` for
OpenRouter `openai/gpt-5.6-luna` under a cumulative $2.00 provider-cost ceiling.
OpenRouter was restricted to the OpenAI provider with fallbacks disabled and
reasoning disabled. The run completed on 2026-08-21:

- 420/420 requests completed on the first attempt;
- zero provider, schema, or parsing errors;
- zero retries;
- actual provider cost: $0.36666348;
- assembled output SHA-256:
  `10b38be6091a37103f1fc8ef33f23090dadf30ef1a3e79e359fce72db6fed577`.

The machine-readable run record is
`annotations/response_validity_human_v2/surrogate_bakeoff_v1/stage_a_run_summary.json`.
Raw append-only responses and the request-ordered assembled file are retained
separately.

## Comparative results

| Configuration | Accuracy | Macro F1 | Refusal P/R/F1 | Capability-failure P/R/F1 | Pivot P/R/F1 | Wrong-language F1 | Refusal–pivot cross-confusion | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Zero-shot joint | .857 | .630 | 1.00/.60/.75 | .840/.913/.875 | 1.00/.333/.500 | .909 | 0 | $0.0379 |
| 7-shot joint | .857 | .644 | 1.00/.60/.75 | .870/.870/.870 | .500/.667/.571 | 1.00 | 0 | $0.0547 |
| 14-shot joint | .869 | .630 | .750/.60/.667 | .875/.913/.894 | .250/.333/.286 | 1.00 | .125 | $0.0818 |
| 14-shot decomposed | .845 | .581 | .750/.60/.667 | .840/.913/.875 | 0/0/0 | 1.00 | .125 | $0.0771 |
| 22-shot error-targeted | **.881** | **.684** | .750/.60/.667 | .875/.913/.894 | .333/.333/.333 | 1.00 | .125 | $0.1151 |

The 22-shot error-targeted prompt has the highest accuracy and macro F1. It is
not an automatic winner for the paper's core refusal outcome: the 7-shot joint
prompt has higher refusal precision and F1, higher pivot F1, zero direct
refusal–pivot cross-confusion, and costs less than half as much. The decomposed
configuration fails to identify any of the three human-coded pivots and should
not advance unchanged. More examples do not monotonically improve the
scientifically important boundary.

All configurations recover only three of five human-coded genuine refusals.
The same two supposed refusals are called coherent answers by every prompt.
The two human-coded ambiguous cases are always classified as incoherent; no
configuration ever predicts the ambiguous class. Wrong-language detection is
essentially solved in this small evaluation set, with perfect F1 for every
few-shot configuration.

## Gold-label audit triggered by the bake-off

There are 18 unique evaluation responses misclassified by at least one
configuration; seven are misclassified by all five. The system disagreements
cannot be interpreted only as model errors. Direct inspection of the seven
persistent rows indicates that several frozen one-coder labels may not follow
the written codebook:

- two human-coded genuine refusals contain direct, substantive answers before
  cautious framing or advice to consult local authorities;
- one human-coded coherent pivot gives a detailed answer after a disclaimer
  about lacking personal opinions;
- one human-coded coherent answer is visibly garbled pseudo-Russian;
- two human-coded ambiguous responses mix an assessable opening with later
  degeneration, revealing an unresolved primary-class precedence rule;
- one Hindi row exposes an incoherence-versus-substantive-pivot boundary.

These are deterministic disagreement cases, not rhetorically selected
examples. Original human labels must remain immutable. Any revised judgment
must be appended as a blinded adjudication with its reason and timestamp.
Because the cases were surfaced by evaluation disagreement, the 84 rows should
thereafter be described as an audit/development set, not a pristine final
holdout. Performance must be reported against both the original freeze and the
adjudicated labels.

## Decision

Do not yet promote a configuration or call GPT-5.6 Luna a validated surrogate.
The next gate is a blinded human adjudication packet containing every response
misclassified by at least one configuration, with special attention to the
seven persistent cases. The interface should hide Luna outputs and the first
human label, collect the component dimensions first, and derive the primary
class through an explicit precedence rule. After adjudication:

1. rescore all five configurations against both original and adjudicated
   labels;
2. repair only genuinely ambiguous codebook boundaries;
3. freeze a new rare-class-enriched holdout that no prompt-development decision
   can inspect;
4. compare only the strongest compact and error-targeted configurations on the
   new holdout before proposing population annotation.

No Gemini, Claude, full-population, or additional paid call is authorized by
this result.

## Subsequent adjudication

All 18 disagreement cases were subsequently recoded through the Streamlit
interface, changing six labels. The rescore and its critical prior-exposure
limitation are documented in
[`STAGE_A_ADJUDICATION_RESULTS.md`](STAGE_A_ADJUDICATION_RESULTS.md). These
development results do not alter the requirement for a new untouched enriched
holdout.
