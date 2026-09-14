#!/usr/bin/env bash
# Historical signpost only. The completed 2026-07 prompt-battery correction
# chain called one-off stages 09--14. Those implementations and their pre-fix
# evidence were archived on 2026-09-01 after the corrected battery was frozen.
# Keeping an apparently runnable wrapper here previously caused a misleading
# failure because its relative Python paths no longer existed in sourcing/.
set -euo pipefail

cat >&2 <<'EOF'
This is a historical, non-executing recipe. It must not be used to rebuild or
modify the frozen prompt battery.

Read:
  docs/TECHNICAL_PIPELINE.md, stage 06
  docs/REBALANCE.md, sections 8--15

Retained implementations:
  archive/2026-09-01_pre_rationalization/sourcing/09_migrate_issue_ids.py
  archive/2026-09-01_pre_rationalization/sourcing/10_backtranslate_native.py
  archive/2026-09-01_pre_rationalization/sourcing/11_retranslate_affected.py
  archive/2026-09-01_pre_rationalization/sourcing/12_normalize_boundary_templates.py
  archive/2026-09-01_pre_rationalization/sourcing/13_recover_qids.py
  archive/2026-09-01_pre_rationalization/sourcing/14_recover_provenance.py

The corrected five-language sample is hash-frozen in
config/replication_contract.json. A new correction must use a new versioned
script and output directory rather than editing those artifacts in place.
EOF
exit 2
