# Retired estimates

Outputs withdrawn because the estimand itself is unsound, not because a newer
version exists. They are kept only so a number in an old draft can be traced.
**Do not quote them, and do not regenerate them without fixing the design.**

| file | why it was retired |
|---|---|
| `e20_moral_by_language.csv` | Compared moral-foundation prevalence across languages **without pairing**. Both passes are conditional on engagement, and engagement rates differ by language, so the denominators are not comparable across languages — the contrast mixes "which foundations get invoked" with "which responses happened to be engaged in that language". A defensible version needs the paired block design of `c08` (block = model × prompt_id) applied to a content outcome, restricted to blocks engaged in **both** languages. That analysis has not been run. `P11_moral_by_language.png`, which plotted this table, was withdrawn with it (`pipeline/archive/precanonical_v1/retired_figures/`). |
