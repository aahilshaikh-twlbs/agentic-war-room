# template/ developer convenience targets.
#
# The `pre-test` target is the CI-time substrate drift guard: it verifies the
# vendored installer substrate (scripts/installer/_substrate/) is byte-identical
# to its warroom_setup/ originals BEFORE the test suite runs. `make test` runs
# it automatically.

PYTHON ?= .venv/bin/python
INSTALLER := scripts/installer

.PHONY: test pre-test substrate-check substrate-sync sanitize

# Drift guard -- runs before the suite (C9/F14).
pre-test:
	bash $(INSTALLER)/sync_substrate.sh --check

substrate-check:
	bash $(INSTALLER)/sync_substrate.sh --check

substrate-sync:
	bash $(INSTALLER)/sync_substrate.sh

sanitize:
	$(PYTHON) scripts/sanitize_check.py

test: pre-test
	$(PYTHON) -m pytest -q
