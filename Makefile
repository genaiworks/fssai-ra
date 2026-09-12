APP_DIR := fssai-ra
SYSTEM_PYTHON ?= python3
VENV := $(APP_DIR)/.venv
PYTHON := $(abspath $(VENV)/bin/python)

.PHONY: help setup check-env demo reviewer test lint check doctor docs-check clean

help:  ## Show the repository-level commands
	@echo "FSSAI-RA — repository commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Create .venv and install development dependencies
	$(SYSTEM_PYTHON) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e "./$(APP_DIR)[dev]"

check-env:
	@test -x "$(PYTHON)" || { \
	  echo "Environment missing. Run: make setup"; \
	  exit 1; \
	}

demo: check-env  ## Run the two-minute offline demonstration
	cd $(APP_DIR) && $(PYTHON) scripts/demo.py

reviewer: check-env  ## Reproduce every review and assurance check
	$(MAKE) -C $(APP_DIR) reviewer PYTHON="$(PYTHON)"

test: check-env  ## Run the deterministic Python suite
	$(MAKE) -C $(APP_DIR) test PYTHON="$(PYTHON)"

lint: check-env  ## Lint source, tests, jobs, and scripts
	$(MAKE) -C $(APP_DIR) lint PYTHON="$(PYTHON)"

check: check-env  ## Run the complete local release-readiness suite
	$(MAKE) -C $(APP_DIR) check PYTHON="$(PYTHON)"

doctor: check-env  ## Explain the active deployment configuration
	$(MAKE) -C $(APP_DIR) doctor PYTHON="$(PYTHON)"

docs-check: check-env  ## Verify links, navigation, and published claims
	cd $(APP_DIR) && $(PYTHON) -m pytest -q tests/test_learning_paths.py tests/test_paper_alignment.py

clean:  ## Remove generated caches and package build output
	$(MAKE) -C $(APP_DIR) clean
