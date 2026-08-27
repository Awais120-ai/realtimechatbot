.PHONY: run dev-db docker-up docker-down migrate test

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-db:
	docker compose -f docker-compose.dev.yml up -d

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

migrate:
	alembic revision --autogenerate -m "auto migration"
	alembic upgrade head

test:
	pytest
