# Python command surface

`SCRIPT_REGISTRY.csv` is the machine-readable inventory of every live Python
file under `scripts/`. Its stage identifiers make the workflow explicit without
renaming importable modules or pretending that support tools run in one linear
sequence.

## Numbering convention

- `G01`--`G05`: original prompt sampling, generation, annotation, assembly and
  embedding production;
- `E01`--`E26`: subject-model expansion contracts; `E03` is the guarded
  new-developer access-smoke stage, `E04` is its 400-response pilot, and `E05`
  is the native Sarvam-105B access smoke; `E06` is the transient-only
  low-concurrency repair, `E07` is the matched Sarvam pilot, and `E08` is their
  shared blinded Luna v2.4 annotation stage; `E09` is its design-weighted Sol
  verification audit; `E10` is the independent full-corpus generation
  contract for the three candidates; `E11` freezes and runs one blinded Luna
  v2.4 annotation contract for each completed full-corpus model; `E12` is the
  isolated local-Q8 smoke for Krutrim, GigaChat3, EuroLLM and Salamandra; `E13`
  is the matched 40-meaning admission pilot for the locally runnable models;
  `E14` is GigaChat's raw-completion repair for its incompatible embedded
  template; `E15` applies that transport to the matched GigaChat pilot; `E16`
  resumes the remaining local pilots in a deliberately sequential order; and
  `E17` freezes and runs their shared blinded Luna v2.4 annotation stage while
  retaining technical no-output records in the generation denominator;
  `E18`--`E20` preserve the completed native Fanar diagnostic, matched pilot
  and probability-sampled English/Arabic route audit. They are retained for
  provenance and are not current instructions to expand Fanar; `E21` is the
  design-weighted Sol verification gate for the four local-model pilots; `E22`
  applies the unchanged v2.4 codebook to every response in the Torch benchmark
  and preserves refusal/capability-failure overlap rather than using capability
  diagnostics as a filter; `E23` sends every Luna-flagged benchmark response
  and probability-sampled clean controls to Sol using identical messages and
  schema, retaining design weights for benchmark-wide accuracy estimates;
  `E24` performs the offline native Fanar system-outcome audit, while `E25`
  freezes and guards the 29-case provider-filter repeatability experiment;
  `E26` applies the unchanged Sol v2.4 codebook to every response newly exposed
  by that retest;
- `V01`: the adopted response-validity command surface;
- `A01`: repository audit;
- `H01`--`H02`: imported helpers, never run as pipeline stages;
- `C01`--`C04`: read-only progress and integrity checks.

The filenames remain descriptive because several are imported as Python
modules. The numbered registry, not an arbitrary filename prefix, defines their
place in the workflow.

## What is live

The original `G` scripts are retained because they reconstruct the original
response and Gemini-annotation inputs. They are completed production
implementations, not authorization to call a provider. `E02` preserves the
exact completed expansion implementation. `E03` screens new developer routes
without producing analysis data; `E04` applies the established enriched pilot
frame to routes that pass that screen. `E05` tests the native replacement for
the deprecated Sarvam generation; `E06` and `E07` preserve the resulting
repair and matched-pilot contracts. `V01` is the only supported
response-validity CLI; its local validation subcommands are listed in
`docs/PIPELINE_ENTRYPOINTS.md`, while paid subcommands remain fail-closed behind
frozen hashes, provider pins, ceilings and explicit authorization.

`scripts/checks/` contains read-only operational inspection tools. None is an
analysis stage and none changes an annotation or response ledger.

## What is not live

- `archive/`: completed pilots, failed provider attempts, superseded DSL tools,
  endpoint setup tests, one-off corrections and the prior cleanup utility.
  These files preserve provenance and are not supported commands.
- `pending/`: code associated with a construct that has not been adopted. The
  stance coder is here because slant/content outcomes remain outside the live R
  release.

No script in `archive/` or `pending/` is imported by the release driver.
