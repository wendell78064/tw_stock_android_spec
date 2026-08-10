.PHONY: up down logs backend-test backend-lint backend-build android-build android-test android-lint android-ui-test-apk openapi-validate openapi-generate test build health migrate migrate-up migrate-down sync-securities sync-daily-prices backfill-security calculate-technicals

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

android-lint:
	docker compose --profile build run --rm android-builder ./gradlew --no-daemon lintDebug

android-ui-test-apk:
	docker compose --profile build run --rm android-builder ./gradlew --no-daemon :app:assembleDebugAndroidTest

openapi-validate:
	docker compose --profile build run --rm android-builder ./gradlew --no-daemon openApiValidate

openapi-generate:
	docker compose --profile build run --rm android-builder ./gradlew --no-daemon openApiGenerate

test: backend-test android-test

build: backend-build android-build

health:
	./scripts/health-check.sh

migrate-up:
	docker compose exec backend alembic upgrade head

migrate: migrate-up

migrate-down:
	docker compose exec backend alembic downgrade -1

sync-securities:
	docker compose exec backend python -m app.cli.sync_securities --provider fake

sync-daily-prices:
	docker compose exec backend python -m app.cli.sync_daily_prices --provider fake --date $(DATE)

backfill-security:
	docker compose exec backend python -m app.cli.sync_daily_prices --provider fake --code $(CODE) --market $(MARKET) --start $(FROM) --end $(TO)

calculate-technicals:
	docker compose exec backend python -m app.cli.sync_daily_prices --provider fake --code $(CODE) --market $(MARKET) --start 2025-01-01 --end 2026-08-07
