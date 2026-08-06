.PHONY: up down logs backend-test backend-lint backend-build android-build android-test test build health migrate-up migrate-down

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f backend

backend-test:
	docker compose run --rm --no-deps backend pytest

backend-lint:
	docker compose run --rm --no-deps backend ruff check app tests

backend-build:
	docker compose build backend

android-build:
	docker compose --profile build run --rm android-builder ./gradlew --no-daemon :app:assembleDebug

android-test:
	docker compose --profile build run --rm android-builder ./gradlew --no-daemon testDebugUnitTest

test: backend-test android-test

build: backend-build android-build

health:
	./scripts/health-check.sh

migrate-up:
	docker compose exec backend alembic upgrade head

migrate-down:
	docker compose exec backend alembic downgrade base

