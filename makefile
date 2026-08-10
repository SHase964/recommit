.PHONY: lint
lint: lint-backend

.PHONY: lint-backend
lint-backend:
	uv run ruff format backend tests
	uv run ruff check --fix backend tests
	uv run mypy backend tests --explicit-package-bases

.PHONY: test
test:
	uv run pytest
