# `30_acceptance.R`

This is the numerical release gate, not an estimator. It sources the common
frame and then reads candidate tables/figures from the environment-selected
release directories.

The first checks bind the release to the registry-defined contract: 299,080 unique
keys across 24 models, the exact original-panel Parquet SHA-256, 7,175 genuine
refusals, 74,598 capability failures, and exact reproduction of the original
Gemini sensitivity on its 137,186-row domain. Further checks enforce the
two-outcome home/language/framing table shapes, bounded
probability differences, common-support diagnostics, v2.4-only stability,
absolute-level/contrast identities, original-to-final transition shares, 2,496
fixed UMAP coordinates, prompt-distribution outputs, and exact
two-main/14-extended PNG inventory. The figure gate also keeps capability
failure out of the main artwork and requires exact multi-model membership in
the combined jurisdiction atlas.
It also verifies that root-level scripts never source `pipeline/pending/` and
that each registered live R file links to a companion document.

Every assertion is accumulated before exit. Outside read-only mode the script
writes `c01b_acceptance_tests.csv`; a failure exits nonzero and prevents
promotion. `CANON_ACCEPT_READONLY=1` permits inspecting an immutable release
without writing into it. Historical `canon_012` should fail the current contract because
it predates v2.4; that is a version mismatch, not a reason to edit history.

Passing this gate means the software outputs conform to declared contracts. It
does not establish causal identification, annotation truth or publication
quality by itself.
