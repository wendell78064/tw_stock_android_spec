.PHONY: up down logs backend-test backend-lint backend-build android-build android-test android-lint android-ui-test-apk openapi-validate openapi-generate test build health migrate migrate-up migrate-down sync-securities sync-daily-prices sync-market-spot backfill-market-spot backfill-security calculate-technicals sync-derivatives sync-futures sync-futures-institutional sync-options sync-vix

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

sync-market-spot:
	docker compose exec backend python -m app.cli.sync_market_spot --provider $(or $(PROVIDER),fake) --date $(DATE)

backfill-market-spot:
	docker compose exec backend python -m app.cli.sync_market_spot --start $(FROM) --end $(TO)

sync-derivatives:
	docker compose exec backend python -m app.cli.sync_derivatives --provider $(or $(PROVIDER),fake) --date $(DATE)

sync-futures:
	docker compose exec backend python -m app.cli.sync_derivatives --provider $(or $(PROVIDER),fake) --date $(DATE) --dataset FUTURES_PRODUCTS --dataset FUTURES_CONTRACTS --dataset FUTURES_DAILY

sync-futures-institutional:
	docker compose exec backend python -m app.cli.sync_derivatives --provider $(or $(PROVIDER),fake) --date $(DATE) --dataset FUTURES_INSTITUTIONAL --dataset TRADER_CONCENTRATION

sync-options:
	docker compose exec backend python -m app.cli.sync_derivatives --provider $(or $(PROVIDER),fake) --date $(DATE) --dataset OPTION_PUT_CALL --dataset OPTION_STRIKE_OI

sync-vix:
	docker compose exec backend python -m app.cli.sync_derivatives --provider $(or $(PROVIDER),fake) --date $(DATE) --dataset VOLATILITY_INDEX
