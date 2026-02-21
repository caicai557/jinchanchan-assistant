.PHONY: smoke

smoke:
	ruff check .
	ruff format --check .
	mypy .
	pytest
