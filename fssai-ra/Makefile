.PHONY: install test api import-api dev-env stack-up stack-down evaluate openapi

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -q

api:
	uvicorn fssaira.api:create_default_app --factory --host 127.0.0.1 --port 8080

import-api:
	uvicorn fssaira.import_api:create_import_app --factory --host 127.0.0.1 --port 8081

dev-env:
	python scripts/bootstrap_dev_env.py

stack-up: dev-env
	docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d

stack-down:
	docker compose --env-file deploy/.env -f deploy/compose.yaml down

evaluate:
	fssaira evaluate profiles/student_support.yaml --output evaluation/results/local.json

openapi:
	python scripts/export_openapi.py
