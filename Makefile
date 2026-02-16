SHELL = /bin/bash


.PHONY: run-test
run-test:
	@echo "Running linters and tests in parallel (uv run)..."
	@status=0; \
	uv run -- ruff check . & p1=$$!; \
	uv run -- ruff format . --check & p2=$$!; \
	uv run -- mypy maxapi & p3=$$!; \
	uv run -- pytest -q & p4=$$!; \
	for p in $$p1 $$p2 $$p3 $$p4; do \
		wait $$p || status=1; \
	done; \
	exit $$status


.PHONY: format
format:
	@echo "Running ruff formatter..."
	uv run ruff format .
