PYTHON ?= python3

.PHONY: install demo test fast lint evidence community rehearsal clean

install:        ## editable install with test tools
	$(PYTHON) -m pip install -e '.[dev]'

demo:           ## the talk: seven scenes, every domain
	$(PYTHON) demo.py

test:           ## every test, including the slow reference-equivalence runs
	$(PYTHON) -m pytest

fast:           ## skip the slow ablation and red-team runs
	$(PYTHON) -m pytest -m 'not slow'

lint:
	$(PYTHON) -m ruff check src tests demo.py examples workshop scripts benchmarks

evidence:       ## regenerate every figure for every world
	for w in $$($(PYTHON) -m trustkernel worlds --ids); do \
	  $(PYTHON) -m trustkernel evidence --world $$w --out evidence/$$w.json; done

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

community:     ## fast attendee artifacts and observable-effect checks
	$(PYTHON) -m workshop.check --implementation solution
	$(PYTHON) examples/effect_oracle.py
	$(PYTHON) examples/replay_boundary.py
	$(PYTHON) examples/generalized_dispatch.py

rehearsal:     ## capture real terminal runs with offline playback
	$(PYTHON) scripts/record_rehearsal.py
