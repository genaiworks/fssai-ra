PYTHON ?= python3

.PHONY: install demo test fast lint evidence clean

install:        ## editable install with test tools
	$(PYTHON) -m pip install -e '.[dev]'

demo:           ## the talk: six scenes against the devtools world
	$(PYTHON) demo.py

test:           ## every test, including the slow reference-equivalence runs
	$(PYTHON) -m pytest

fast:           ## skip the slow ablation and red-team runs
	$(PYTHON) -m pytest -m 'not slow'

lint:
	$(PYTHON) -m ruff check src tests demo.py

evidence:       ## regenerate every figure for both worlds
	$(PYTHON) -m trustkernel evidence --world devtools --out evidence/devtools.json
	$(PYTHON) -m trustkernel evidence --world education --out evidence/education.json

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
