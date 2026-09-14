PYTHON ?= python3

.PHONY: help install test lint results figures demo check api gateway console dev-env \
        stack-up stack-down verify evaluate conformance doctor openapi clean adaptive \
        reviewer oversight challenge second-domain domain-packs disclosure threats thesis lab

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package with development extras
	$(PYTHON) -m pip install -e ".[dev]"

test:  ## Run the deterministic test suite
	$(PYTHON) -m pytest

lint:  ## Lint the Python sources
	$(PYTHON) -m ruff check src tests scripts jobs adapters

verify:  ## Bounded model check of the reference profile
	$(PYTHON) -m fssaira.cli verify profiles/student_support.yaml

evaluate:  ## Adversarial scenarios, utility baseline, and ablations
	$(PYTHON) -m fssaira.cli evaluate profiles/student_support.yaml

oversight:  ## What review can this roster actually supply, and does the control bind?
	$(PYTHON) -m fssaira.cli oversight profiles/student_support.yaml --sweep

challenge:  ## Score the open adversary corpus against all three architectures
	$(PYTHON) -m fssaira.cli challenge --dir challenges

second-domain:  ## The identical suite against a domain it was not designed for
	$(PYTHON) -m fssaira.cli verify profiles/academic_record_correction.yaml
	$(PYTHON) -m fssaira.cli evaluate profiles/academic_record_correction.yaml
	$(PYTHON) -m fssaira.cli conformance --profile profiles/academic_record_correction.yaml

thesis:  ## Try to refute the Mediation Thesis across every domain pack
	$(PYTHON) -m fssaira.cli thesis

threats:  ## Alignment failures and AI threats: contained, bounded, residual, with evidence checked to exist
	$(PYTHON) -m fssaira.cli threats

disclosure:  ## What may a model read and release? Every pack that declares a disclosure policy
	$(PYTHON) -m fssaira.cli disclosure profiles/healthcare_record_access.yaml
	$(PYTHON) -m fssaira.cli disclosure profiles/corporate_confidential_data.yaml
	$(PYTHON) -m fssaira.cli disclosure profiles/financial_consumer_data.yaml
	$(PYTHON) -m fssaira.cli disclosure profiles/government_benefits.yaml

domain-packs:  ## Validate and verify every education, corporate, healthcare, financial, and government pack
	$(PYTHON) -m fssaira.cli profiles --verify

lab:  ## Open the two browser tools used by docs/LAB.md
	@echo "  worksheet   docs/worksheet/index.html"
	@echo "  calculator  docs/oversight/index.html"
	@$(PYTHON) -c "import pathlib,webbrowser; [webbrowser.open(pathlib.Path(p).resolve().as_uri()) for p in ('docs/worksheet/index.html','docs/oversight/index.html')]"

reviewer:  ## Everything a reviewer should check, in one command
	@echo "── 1/14  the suite ───────────────────────────────────────────────"
	@$(PYTHON) -m pytest -q
	@echo "── 2/14  what this deployment really is ──────────────────────────"
	@$(PYTHON) -m fssaira.cli doctor || true
	@echo "── 3/14  is each contract requirement enforced, or written down? ─"
	@$(PYTHON) -m fssaira.cli coverage
	@echo "── 4/14  bounded model check, reference domain ───────────────────"
	@$(PYTHON) -m fssaira.cli verify profiles/student_support.yaml
	@echo "── 5/14  containment, utility, and ablation ──────────────────────"
	@$(PYTHON) -m fssaira.cli evaluate profiles/student_support.yaml
	@echo "── 6/14  the first transfer test and defect it exposed ───────────"
	@$(MAKE) second-domain PYTHON="$(PYTHON)"
	@echo "── 7/14  every reusable domain pack, independently reported ──────"
	@$(MAKE) domain-packs PYTHON="$(PYTHON)"
	@echo "── 7b/14  the read path: governed disclosure ─────────────────────"
	@$(MAKE) disclosure PYTHON="$(PYTHON)"
	@echo "── 7c/14  does the safety case depend on alignment? ──────────────"
	@$(MAKE) threats PYTHON="$(PYTHON)"
	@echo "── 7d/14  can anyone refute the thesis? ──────────────────────────"
	@$(MAKE) thesis PYTHON="$(PYTHON)"
	@echo "── 8/14  portable conformance on memory and SQL backends ─────────"
	@$(MAKE) conformance PYTHON="$(PYTHON)"
	@echo "── 9/14  how much oversight can actually be supplied ─────────────"
	@$(PYTHON) -m fssaira.cli oversight profiles/student_support.yaml --sweep
	@echo "── 10/14  what a review assistant does to that answer ────────────"
	@$(PYTHON) -m fssaira.cli assisted-review profiles/student_support.yaml
	@echo "── 11/14  authority that travels: delegation chains ──────────────"
	@$(PYTHON) -m fssaira.cli delegation
	@echo "── 12/14  the open adversary corpus ──────────────────────────────"
	@$(PYTHON) -m fssaira.cli challenge --dir challenges
	@echo "── 13/14  do process races and recovery match their source? ──────"
	@$(PYTHON) scripts/check_resilience.py
	@echo "── 14/14  do the committed numbers match a fresh run? ────────────"
	@$(PYTHON) scripts/generate_results.py --check
	@echo ""
	@echo "  Every figure above is regenerated, not typed. If any of it disagrees"
	@echo "  with the paper, the paper is wrong and we would like to know."

conformance:  ## Conformance on both backend profiles
	$(PYTHON) -m fssaira.cli conformance --backend memory --profile profiles/student_support.yaml
	$(PYTHON) -m fssaira.cli conformance --backend sql --profile profiles/student_support.yaml

doctor:  ## Report what this deployment actually is
	$(PYTHON) -m fssaira.cli doctor

demo:  ## The two-minute hero demonstration (fully offline)
	$(PYTHON) scripts/demo.py

conference-demo:  ## The UNU Macau live demonstration: a malicious AI, nine demos (offline)
	$(PYTHON) scripts/conference_demo.py $(if $(DEMO),--demo $(DEMO),)

security:  ## Kernel floor, education pack failure tests, privacy custody, and conference tests
	$(PYTHON) -m pytest -q tests/test_education_pack.py tests/test_privacy_custody.py tests/test_conference_falsification.py
	$(PYTHON) -m fssaira.cli conference pack-check conference/attacks/malicious-domain-pack.yaml || true

falsify:  ## Run every falsifier, or one: make falsify F=F19
	$(PYTHON) -m fssaira.cli conference falsify $(F)

adaptive:  ## Offline adaptive attacker vs static/random, independent oracle (add PROVE=1)
	$(PYTHON) -m fssaira.cli conference adaptive $(if $(PROVE),--prove-attacker,)

ablation:  ## Enabled / disabled / restored for every control, or one falsifier: make ablation F=F10
	$(PYTHON) -m fssaira.cli conference ablation $(F)

conference:  ## Regenerate conference/evidence from a real run
	$(PYTHON) scripts/conference_evidence.py

conference-check:  ## Do the committed conference figures match a fresh run?
	$(PYTHON) scripts/conference_evidence.py --check

results:  ## Regenerate every figure the paper and the deck quote
	$(PYTHON) scripts/generate_results.py

figures:  ## Regenerate the deck's charts from the experiment results
	$(PYTHON) scripts/generate_figures.py

check: lint reviewer  ## Run the complete local release-readiness suite
	$(PYTHON) scripts/demo.py --fast > /dev/null

api:  ## Serve the control plane on 127.0.0.1:8080
	$(PYTHON) -m fssaira.cli serve --host 127.0.0.1 --port 8080

gateway:  ## Serve the low-side import gateway on 127.0.0.1:8081
	$(PYTHON) -m fssaira.cli serve --gateway --host 127.0.0.1 --port 8081

console:  ## Run the React console against a local control plane
	cd console && npm install --no-audit --no-fund && npm run dev

dev-env:  ## Generate deploy/.env from the example
	$(PYTHON) scripts/bootstrap_dev_env.py

stack-up: dev-env  ## Bring up the reference deployment
	docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d

stack-down:  ## Tear it down
	docker compose --env-file deploy/.env -f deploy/compose.yaml down

openapi:  ## Export the OpenAPI schema
	$(PYTHON) scripts/export_openapi.py

clean:  ## Remove build and cache artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info src/*.egg-info
