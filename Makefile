.PHONY: up down logs migrate test seed fmt

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api worker web

migrate:
	docker compose exec api alembic upgrade head

test:
	docker compose exec api pytest -q

seed:
	docker compose exec api python -m app.simulation.seed

fmt:
	docker compose exec api ruff check --fix app tests
