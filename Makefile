test:
	python -m pytest
format:
	ruff format .
frontend-install:
	npm --prefix frontend install
frontend-dev:
	npm --prefix frontend run dev
frontend-build:
	npm --prefix frontend run build
