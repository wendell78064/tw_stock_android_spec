import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.cli.smoke_realtime_quote import _validate_event, parse_args, smoke
from app.domain.realtime import (
    DataStatus,
    RealtimeBidAsk,
    RealtimeQuote,
    RealtimeQuoteType,
)


def _tick() -> RealtimeQuote:
    now = datetime.now(UTC)
    return RealtimeQuote(
        security_id="sec_2330",
        market_id="TWSE",
        code="2330",
        exchange_timestamp=now,
        received_at=now,
        last_price=Decimal("100.5"),
        data_status=DataStatus.LIVE,
        provider="SINOPAC_SHIOAJI",
    )


@pytest.mark.asyncio
async def test_smoke_timeout_is_bounded_and_always_unsubscribes(capsys):
    provider = SimpleNamespace(
        connect=AsyncMock(),
        resolve_contract=lambda _key: object(),
        acquire_subscription=AsyncMock(),
        wait_for_event=AsyncMock(side_effect=TimeoutError),
        release_subscription=AsyncMock(),
        close=AsyncMock(),
    )
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            smoke(provider, "TWSE", "2330", RealtimeQuoteType.TICK, 0.01), 0.1
        )
    provider.release_subscription.assert_awaited_once()
    provider.close.assert_awaited_once()
    assert "secret" not in capsys.readouterr().out.lower()


@pytest.mark.asyncio
async def test_smoke_success_prints_only_bounded_stage_results(capsys):
    provider = SimpleNamespace(
        connect=AsyncMock(),
        resolve_contract=lambda _key: object(),
        acquire_subscription=AsyncMock(),
        wait_for_event=AsyncMock(return_value=_tick()),
        release_subscription=AsyncMock(),
        close=AsyncMock(),
    )
    await smoke(provider, "TWSE", "2330", RealtimeQuoteType.TICK, 0.1)
    output = capsys.readouterr().out
    assert output.splitlines() == [
        "LOGIN=PASS",
        "CONTRACT=PASS",
        "SUBSCRIBE=PASS",
        "EVENT=PASS",
        "UNSUBSCRIBE=PASS",
    ]
    assert "api" not in output.lower() and "secret" not in output.lower()


def test_bidask_validation_and_unsupported_security_arguments(monkeypatch):
    now = datetime.now(UTC)
    event = RealtimeBidAsk(
        market_id="TPEx",
        code="6488",
        exchange_timestamp=now,
        received_at=now,
        bid_prices=[Decimal("88.7")],
        bid_volumes=[2],
        ask_prices=[Decimal("88.9")],
        ask_volumes=[3],
        provider="SINOPAC_SHIOAJI",
    )
    _validate_event(event, RealtimeQuoteType.BID_ASK, "TPEX", "6488")
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke",
            "--market",
            "TWSE",
            "--code",
            "23X0",
            "--quote-type",
            "tick",
        ],
    )
    with pytest.raises(SystemExit):
        parse_args()
