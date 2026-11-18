PYTHON ?= python
export PYTHONPATH := src

.PHONY: install lint format test test-unit test-integration test-e2e coverage coverage-gate load run clean

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

test-unit:
	$(PYTHON) -m pytest tests/unit --cov=wallet --cov-branch --cov-report= --cov-fail-under=0 --junitxml=reports/junit/unit.xml

test-integration:
	$(PYTHON) -m pytest tests/integration --cov=wallet --cov-branch --cov-append --cov-report= --cov-fail-under=0 --junitxml=reports/junit/integration.xml

test-e2e:
	$(PYTHON) -m pytest tests/e2e --cov=wallet --cov-branch --cov-append --cov-report= --cov-fail-under=0 --junitxml=reports/junit/e2e.xml

test: test-unit test-integration test-e2e

coverage: test
	$(PYTHON) -m coverage report
	$(PYTHON) -m coverage html
	$(PYTHON) -m coverage xml
	$(PYTHON) -m coverage json

coverage-gate: coverage
	$(PYTHON) scripts/check_coverage.py --lines 85 --branches 80

load:
	scripts/run_load_test.sh $(or $(LOAD_DURATION),30s) $(or $(LOAD_USERS),50)

run:
	$(PYTHON) -m uvicorn wallet.main:app --reload

clean:
	rm -rf reports .coverage .pytest_cache .ruff_cache
