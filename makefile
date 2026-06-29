.PHONY: lint
lint: lint-backend

.PHONY: lint-backend
lint-backend:
	uv run ruff format backend
	uv run ruff check --fix backend
	uv run mypy backend --explicit-package-bases
