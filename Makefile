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
	$(PYTHON) -m pip install -e "./$(APP_DIR)[dev,privacy,api]"

check-env:
	@test -x "$(PYTHON)" || { \
	  echo "Environment missing. Run: make setup"; \
	  exit 1; \
	}

demo: check-env  ## Run the two-minute offline demonstration
	cd $(APP_DIR) && $(PYTHON) scripts/demo.py

security: check-env  ## Adversarial and kernel-floor tests for the conference layer
	$(MAKE) -C $(APP_DIR) security PYTHON="$(PYTHON)"

falsify: check-env  ## Every falsifier, or one: make falsify F=F19
	$(MAKE) -C $(APP_DIR) falsify PYTHON="$(PYTHON)" F="$(F)"

ablation: check-env  ## Enabled / disabled / restored per control: make ablation F=F10
	$(MAKE) -C $(APP_DIR) ablation PYTHON="$(PYTHON)" F="$(F)"

results: check-env  ## Regenerate paper figures and the conference evidence package
	$(MAKE) -C $(APP_DIR) results PYTHON="$(PYTHON)"
	$(MAKE) -C $(APP_DIR) conference PYTHON="$(PYTHON)"

conference-demo: check-env  ## The UNU Macau live demonstration (DEMO=7 for one)
	$(MAKE) -C $(APP_DIR) conference-demo PYTHON="$(PYTHON)" DEMO="$(DEMO)"

reviewer: check-env  ## Reproduce every review and assurance check
	$(MAKE) -C $(APP_DIR) reviewer PYTHON="$(PYTHON)"

test: check-env  ## Run the deterministic Python suite
	$(MAKE) -C $(APP_DIR) test PYTHON="$(PYTHON)"

lint: check-env  ## Lint source, tests, jobs, and scripts
	$(MAKE) -C $(APP_DIR) lint PYTHON="$(PYTHON)"

check: check-env  ## Lint and public assurance checks
	$(MAKE) -C $(APP_DIR) check PYTHON="$(PYTHON)"

doctor: check-env  ## Explain the active deployment configuration
	$(MAKE) -C $(APP_DIR) doctor PYTHON="$(PYTHON)"

docs-check: check-env  ## Verify public documentation, navigation, and software citation
	$(PYTHON) $(APP_DIR)/scripts/check_public_docs.py
	cd $(APP_DIR) && $(PYTHON) -m pytest -q tests/test_learning_paths.py

clean:  ## Remove generated caches and package build output
	$(MAKE) -C $(APP_DIR) clean

.PHONY: all architecture-check
all: check-env  ## Complete public engineering and evidence checks
	$(MAKE) -C $(APP_DIR) all PYTHON="$(PYTHON)"

architecture-check: check-env  ## Architecture traceability and executed capability contracts
	$(MAKE) -C $(APP_DIR) architecture-check PYTHON="$(PYTHON)"

.PHONY: reproduce manuscript-check
reproduce: check-env  ## Reproduce public workflows and save a fresh evidence bundle
	$(MAKE) -C $(APP_DIR) reproduce PYTHON="$(PYTHON)"

manuscript-check: check-env  ## Optional private manuscript checks; requires local-only archives
	$(MAKE) -C $(APP_DIR) manuscript-check PYTHON="$(PYTHON)"

.PHONY: docker-setup docker-reproduce docker-verify docker-shell
# Host ownership for bind-mounted evidence on Linux; override for other platforms.
export LOCAL_UID ?= $(shell id -u)
export LOCAL_GID ?= $(shell id -g)
docker-setup:  ## Build the pinned research toolchain (requires Docker Engine + Compose)
	docker compose build research

docker-reproduce:  ## Run the offline research workflows in Docker
	docker compose run --rm research python scripts/reproduce.py

docker-verify:  ## Full public test, claim-drift and evidence verification in Docker
	docker compose run --rm research python scripts/reproduce.py --full --timeout 1800

docker-shell:  ## Open the research environment to test your own use case
	docker compose run --rm research sh
