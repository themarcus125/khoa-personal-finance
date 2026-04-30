start:
	python finance_bot.py

dev:
	watchfiles "python finance_bot.py"

lint:
	ruff check .

lint-fix:
	ruff check --fix . && ruff format .
