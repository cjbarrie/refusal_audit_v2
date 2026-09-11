# Archived appendix analyses (invalid inference)

These five scripts were retired because their **inferential** content is not
valid for this design. Their descriptive content survives, recomputed, in
`pipeline/40_appendix_descriptives.R`, which produces only descriptive views and
labelled sensitivities of named canonical estimands — never a competing
inferential surface.

They are kept because several numbers in earlier drafts came from them and a
reader who finds an old table needs to be able to trace it. **Do not run them to
produce new results and do not cite their outputs.**

## What was wrong, file by file

| file | defect |
|---|---|
| `43_appendix_deepseek_chinese.R` | `chisq.test` / `fisher.test` comparing English and Chinese responses to the **same prompts**. Those are paired observations on one issue, not two independent samples: the test's null and its variance are both wrong, and the p-values are anti-conservative. It also fits `glm(refused ~ lang_zh * category)` with no clustering, so every standard error treats 2,496 prompts from 624 issues as independent. |
| `44_appendix_deepseek_stats.R` | Bootstrap odds-ratio intervals resampling **rows**. The design clusters responses within issues; a row-level bootstrap understates between-issue variance, and the intervals are too narrow by construction. Also runs BH correction over a family of tests whose individual validity is the problem. |
| `42_appendix_deepseek_language.R` | Uses `response_language` as the exposure. The estimand concerns the **assigned prompt language**; a model that answers an Arabic prompt in English is not an English observation, and conditioning on the realized reply language conditions on a post-treatment variable. |
| `40_appendix_engagement.R` | Unclustered `glm` interaction model, and an editorial line printed into the output ("This is opposite of what you'd expect from a Chinese model!") that states a prior expectation as a finding. |
| `41_appendix_justifications.R` | Descriptive composition tables only — no invalid inference — but it reported the A–G justification codes without the agreement statistics that qualify them. Superseded by the descriptive script for consistency. |

## What replaces each quantity

| retired quantity | canonical replacement |
|---|---|
| DeepSeek English-vs-Chinese refusal difference | `c08`/`c09`: paired within `model x prompt_id`, issue-clustered. The DeepSeek row of `c09` is the same comparison, done correctly. |
| per-category language tests | `c09` heterogeneity rows; no per-category hypothesis tests are reported, because the design supports estimation with intervals, not a family of independent-sample tests. |
| engagement by model x language | descriptive composition in `40_appendix_descriptives.R`, explicitly labelled descriptive. |
| justification composition | descriptive composition, now carried **with** the pairwise agreement statistics from `e23`/`e23b`, because the codes have the weakest agreement of any construct here. |
