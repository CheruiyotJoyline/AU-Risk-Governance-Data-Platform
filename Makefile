.PHONY: env up down reset logs ps psql test lint

env:            ## Create .env with random secrets
	python3 scripts/make_env.py

up:             ## Build images and start the stack
	docker compose up -d --build

down:           ## Stop the stack, keep data
	docker compose down

reset:          ## Stop the stack and delete all data (re-runs the Postgres init script)
	docker compose down -v

logs:           ## Follow logs for all services
	docker compose logs -f

ps:             ## Show service health
	docker compose ps

psql:           ## Open psql on the warehouse as the postgres superuser
	docker compose exec postgres psql -U postgres -d warehouse

test:           ## Run unit tests
	pytest -q

lint:           ## Run every pre-commit hook on every file
	pre-commit run --all-files
