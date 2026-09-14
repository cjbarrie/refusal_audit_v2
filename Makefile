PYTHON ?= python3
RSCRIPT ?= Rscript
NODE_DIR := interactive/web
CANDIDATE_RELEASE ?= canon_031

.PHONY: help baseline-check private-repo-preflight python-tests r-candidate-test audit web-test check candidate-release interactive-data interactive-web

help:
	@printf '%s\n' \
	  'Safe local targets (no provider calls):' \
	  '  make baseline-check       Verify frozen prompts, outcomes and canon_024' \
	  '  make private-repo-preflight Check prospective Git files for size and secrets' \
	  '  make python-tests         Run the repository Python tests' \
	  '  make r-candidate-test     Test the current 24-model R code against canon_031' \
	  '  make web-test             Test data builders and build the web explorer' \
	  '  make audit                Rebuild docs/ARTIFACT_REGISTRY.csv' \
	  '  make check                Run all of the above except the artifact rewrite' \
	  '  make interactive-data     Rebuild Streamlit and web data from the promoted release' \
	  '  make interactive-web      Start the standalone local web explorer' \
	  '' \
	  'Explicit release target (still makes no provider call):' \
	  '  make candidate-release RUN_ID=canon_XXX'

baseline-check:
	$(PYTHON) scripts/replication_check.py

private-repo-preflight:
	$(PYTHON) scripts/private_repo_preflight.py

python-tests:
	$(PYTHON) -m pytest -q

r-candidate-test:
	CANONICAL_RUN_ID=$(CANDIDATE_RELEASE) \
	CANON_DATA_PATH=pipeline/releases/$(CANDIDATE_RELEASE)/estimates/data_clean.RData \
	CANON_EST_DIR=pipeline/releases/$(CANDIDATE_RELEASE)/estimates \
	$(RSCRIPT) pipeline/tests_synthetic.R

web-test:
	$(PYTHON) -m pytest -q interactive/tests
	cd $(NODE_DIR) && npm run lint && npm run build

check: baseline-check python-tests r-candidate-test web-test

audit:
	$(PYTHON) scripts/audit_repository.py

candidate-release:
	@test -n "$(RUN_ID)" || (printf '%s\n' 'RUN_ID is required, e.g. make candidate-release RUN_ID=canon_032'; exit 2)
	CANONICAL_RUN_ID=$(RUN_ID) $(RSCRIPT) pipeline/make_release.R --no-promote

interactive-data:
	$(PYTHON) interactive/build_data.py
	$(PYTHON) interactive/build_web_data.py

interactive-web:
	cd $(NODE_DIR) && npm run dev -- --host 127.0.0.1
