start:
	python finance_bot.py

dev:
	watchfiles --filter python "python finance_bot.py" $(wildcard *.py)

lint:
	ruff check .

lint-fix:
	ruff check --fix . && ruff format .
