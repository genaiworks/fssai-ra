.PHONY: help install test lint results figures demo check api gateway console dev-env \
        stack-up stack-down verify evaluate conformance doctor openapi clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package with development extras
	python -m pip install -e ".[dev]"

test:  ## Run the deterministic test suite
	python -m pytest

lint:  ## Lint the Python sources
	ruff check src tests scripts jobs

verify:  ## Bounded model check of the reference profile
	python -m fssaira.cli verify profiles/student_support.yaml

evaluate:  ## Adversarial scenarios, utility baseline, and ablations
	python -m fssaira.cli evaluate profiles/student_support.yaml

conformance:  ## Conformance on both backend profiles
	python -m fssaira.cli conformance --backend memory --profile profiles/student_support.yaml
	python -m fssaira.cli conformance --backend sql --profile profiles/student_support.yaml

doctor:  ## Report what this deployment actually is
	python -m fssaira.cli doctor

demo:  ## The two-minute hero demonstration (fully offline)
	python scripts/demo.py

results:  ## Regenerate every figure the paper and the deck quote
	python scripts/generate_results.py

figures:  ## Regenerate the deck's charts from the experiment results
	python scripts/generate_figures.py

check: test lint verify evaluate conformance  ## Everything CI runs
	python scripts/demo.py --fast > /dev/null
	python scripts/generate_results.py --check

api:  ## Serve the control plane on 127.0.0.1:8080
	python -m fssaira.cli serve --host 127.0.0.1 --port 8080

gateway:  ## Serve the low-side import gateway on 127.0.0.1:8081
	python -m fssaira.cli serve --gateway --host 127.0.0.1 --port 8081

console:  ## Run the React console against a local control plane
	cd console && npm install --no-audit --no-fund && npm run dev

dev-env:  ## Generate deploy/.env from the example
	python scripts/bootstrap_dev_env.py

stack-up: dev-env  ## Bring up the reference deployment
	docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d

stack-down:  ## Tear it down
	docker compose --env-file deploy/.env -f deploy/compose.yaml down

openapi:  ## Export the OpenAPI schema
	python scripts/export_openapi.py

clean:  ## Remove build and cache artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info src/*.egg-info
