# Protected surrogate evaluation results

Status: complete and scored, 2026-08-24.

## What was compared

The experiment compared the already-frozen `zero_shot_joint_v1` and
`fewshot_error_targeted_22_v1` prompts using `openai/gpt-5.6-luna`. The
evaluation arm contains 116 human-coded responses assigned to that arm before
human coding. Each response was evaluated under both prompts, giving 232
requests. The payload was pinned to the OpenAI provider through OpenRouter;
reasoning and provider fallbacks were disabled.

Provider payload SHA-256:
`b40db8fcab9a7617cd8216f728724357ae01af187fe7080dd2bace5963c772a9`.

Assembled result SHA-256:
`3cf5a1e781182a18f55707668993a009e06bc97910291837db378faf5d77b0bc`.

The human labels were never included in a request. Predictions were joined to
the protected labels only after all 232 schema-valid outputs had been
assembled. This arm is enriched for difficult and rare outcomes, so these are
instrument-performance summaries, not population prevalence estimates.

## Principal results

| Metric | Zero-shot | 22-shot |
|---|---:|---:|
| Primary-class accuracy | 0.7759 | 0.8103 |
| Genuine-refusal precision | 0.9091 | 1.0000 |
| Genuine-refusal recall | 0.5556 | 0.5556 |
| Genuine-refusal F1 | 0.6897 | 0.7143 |
| Capability-failure precision | 0.9459 | 0.8837 |
| Capability-failure recall | 0.8333 | 0.9048 |
| Capability-failure F1 | 0.8861 | 0.8941 |
| Principal selection score | 0.7839 | 0.8062 |

The implementation-frozen principal score is the unweighted mean of genuine-
refusal F1, capability-failure F1 and primary-class accuracy. Coherent pivot
is diagnostic and does not enter this score. On that rule, the 22-shot prompt
advances provisionally.

The choice is modest rather than decisive. Across the paired 116 responses,
both prompts were correct on 85 and wrong on 17. The 22-shot prompt corrected
nine cases missed by zero-shot but introduced five errors on cases zero-shot
classified correctly. Its lower seven-class macro-F1 (0.5962 versus 0.6480)
also shows that the aggregate selection result should not be read as dominance
for every sparse diagnostic category.

## Material failure: refusal recall

The 22-shot prompt found only ten of 18 human-coded genuine refusals. Its eight
false negatives were classified as four coherent answers, two coherent pivots
and two incoherent/garbled responses. Precision was perfect on this small arm,
but recall of 0.5556 is inadequate for population deployment without
design-based correction and likely too inefficient even as a DSL auxiliary
prediction.

Review of the eight errors identifies one common boundary rather than eight
unrelated mistakes. Every response communicates unwillingness or inability to
provide a requested personal stance or advocacy component and then supplies
context, balance, or an adjacent substantive discussion. The v2.1 boundary
rule says that a disclaimer followed by content remains a refusal when the
response communicates that some requested component will not or cannot be
performed. The surrogate is instead over-applying the simpler rule that any
substantive content makes the response an answer or pivot. This is the first
prompt-revision target. It does not justify changing the human labels after
seeing model disagreement.

Descriptively, all seven English refusals were recovered, compared with three
of 11 refusals across Arabic, Hindi, Russian and Chinese. Individual language
cells contain only one to five refusals, so these are diagnostics rather than
stable language-specific reliability estimates. They nevertheless identify
multilingual refusal recall as the next development target.

The 22-shot prompt performed substantially better for aggregate capability
failure: it recovered 38 of 42 cases, with F1 0.8941. It also identified all
ten cases for which the human primary class was wrong language.

## Language-fidelity measurement caveat

The enrichment interface separately recorded `language_fidelity` only when a
case was judged wrong language; most remaining rows carry the sentinel
`not_separately_coded`. That sentinel is missing-by-design, not a prediction
class. The shared scorer was corrected to exclude it from language-fidelity
accuracy. Both prompts match all ten separately coded wrong-language outcomes,
but this cannot be interpreted as full four-category language-fidelity
accuracy.

## Cost and routing

All 232 calls completed without retries. OpenRouter reports platform cost zero
because this is a BYOK route and separately exposes the upstream OpenAI charge.
The upstream charges total $0.20663445, safely below the authorized $2.22 hard
ceiling. The runner now uses upstream cost for both live ceiling enforcement
and resumable reconstruction when `is_byok=true`; the append-only raw provider
records were preserved.

## Decision and next gate

The 22-shot configuration is the current provisional candidate, but it should
not yet label all 137,186 responses. The protected arm is now spent and must
not be reused for iterative prompt selection.

The next proposed stage is:

1. inspect refusal false negatives and multilingual errors as development
   evidence, focusing on explicit partial noncompliance followed by substantive
   content;
2. revise the prompt or examples using development rows only;
3. annotate and freeze a new protected subset from the untouched review orders
   201--400 under a logged protocol amendment;
4. require materially improved multilingual refusal recall while maintaining
   capability-failure performance; and
5. only then estimate and seek authorization for population annotation.

No further human work or provider transmission is authorized by the completed
232-request approval.
