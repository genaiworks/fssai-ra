.PHONY: help install test lint results figures demo check api gateway console dev-env \
        stack-up stack-down verify evaluate conformance doctor openapi clean \
        reviewer oversight challenge second-domain lab

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

oversight:  ## What review can this roster actually supply, and does the control bind?
	python -m fssaira.cli oversight profiles/student_support.yaml --sweep

challenge:  ## Score the open adversary corpus against all three architectures
	python -m fssaira.cli challenge --dir challenges

second-domain:  ## The identical suite against a domain it was not designed for
	python -m fssaira.cli verify profiles/academic_record_correction.yaml
	python -m fssaira.cli evaluate profiles/academic_record_correction.yaml
	python -m fssaira.cli conformance --profile profiles/academic_record_correction.yaml

lab:  ## Open the two browser tools used by docs/LAB.md
	@echo "  worksheet   docs/worksheet/index.html"
	@echo "  calculator  docs/oversight/index.html"
	@python -c "import pathlib,webbrowser; [webbrowser.open(pathlib.Path(p).resolve().as_uri()) for p in ('docs/worksheet/index.html','docs/oversight/index.html')]"

reviewer:  ## Everything a reviewer should check, in one command
	@echo "── 1/8  the suite ────────────────────────────────────────────────"
	@python -m pytest -q
	@echo "── 2/8  what this deployment really is ───────────────────────────"
	-@python -m fssaira.cli doctor
	@echo "── 3/8  bounded model check, reference domain ────────────────────"
	@python -m fssaira.cli verify profiles/student_support.yaml
	@echo "── 4/8  containment, utility, and ablation ───────────────────────"
	@python -m fssaira.cli evaluate profiles/student_support.yaml
	@echo "── 5/8  the same suite on a domain it was not designed for ───────"
	@python -m fssaira.cli verify profiles/academic_record_correction.yaml
	@echo "── 6/8  how much oversight can actually be supplied ──────────────"
	@python -m fssaira.cli oversight profiles/student_support.yaml --sweep
	@echo "── 7/8  the open adversary corpus ────────────────────────────────"
	@python -m fssaira.cli challenge --dir challenges
	@echo "── 8/8  do the committed numbers match a fresh run? ──────────────"
	@python scripts/generate_results.py --check
	@echo ""
	@echo "  Every figure above is regenerated, not typed. If any of it disagrees"
	@echo "  with the paper, the paper is wrong and we would like to know."

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
