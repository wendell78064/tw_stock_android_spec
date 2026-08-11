# Current Project Status

> 後續 Codex Slice 應優先閱讀本文件，再依工作範圍讀取直接相關規格與原始碼；不需預設重讀全部歷史 Phase 文件。

## Completion Summary

```text
Phase 0 COMPLETE
Phase 1 COMPLETE
Phase 2 COMPLETE
Phase 3 / Slice 1 COMPLETE
Phase 3 / Slice 2 COMPLETE
```

Latest completed:

```text
Phase 3 / Slice 2 — Watchlist Core
```

Database head:

```text
0007_watchlist_core
```

Latest tag:

```text
phase-3-slice-2-complete
```

## Current Release Baseline

- Branch：`master`
- Phase 3／Slice 2 feature commit：`2fe7e2d882079cf916ab6c3e704e4e33c9ad2baf`
- Instrumentation selector fix：`a9fbe3d`
- Final closeout：以 `phase-3-slice-2-complete` tag 為準
- GitHub Actions：PASS
- Backend job：PASS
- Android job：PASS
- Android instrumentation job：PASS
- Emulator API：35
- Emulator target：Google APIs
- Emulator architecture：x86_64

## Current Phase

- Phase 3 / Slice 2：COMPLETE
- Latest completed feature：Watchlist Core
- Feature commit：`2fe7e2d882079cf916ab6c3e704e4e33c9ad2baf`
- Latest completed tag：`phase-3-slice-2-complete`
- Database head：`0007_watchlist_core`
- Next：Phase 3 / Slice 3 — Alert Engine

## Completed Watchlist Capabilities

- Watchlist groups
- Create / rename / delete group
- Watchlist item CRUD
- Same security in multiple groups
- Manual reorder
- Note
- Target price
- Stop price
- Add price
- Daily price enrichment
- Technical summary
- Institutional summary
- Credit summary
- Room offline cache
- Offline / Stale / Partial

## Completed Portfolio Capabilities

- Portfolio
- BUY / SELL transactions
- Moving average cost
- Current positions
- Realized P&L
- Unrealized P&L
- Market value
- Return %
- Portfolio summary
- Security allocation
- Transaction history
- Holding detail
- Offline read cache

## Current Portfolio APIs

- `GET /v1/portfolios`
- `POST /v1/portfolios`
- `GET /v1/portfolios/{portfolioId}`
- `GET /v1/portfolios/{portfolioId}/transactions`
- `POST /v1/portfolios/{portfolioId}/transactions`
- `DELETE /v1/portfolios/{portfolioId}/transactions/{transactionId}`
- `GET /v1/portfolios/{portfolioId}/positions`
- `GET /v1/portfolios/{portfolioId}/summary`

## Android Modules

- `app`
- `core-model`
- `core-network`
- `core-database`
- `core-ui`
- `feature-market`
- `feature-security`
- `feature-portfolio`
- `feature-watchlist`

## Phase 2 / Slice 2 Scope

- 臺灣衍生品盤後日資料
- TX、MTX、TMF、TE、TF futures products
- 實際年月 contracts
- Futures daily OHLC
- Settlement price
- Volume
- Open interest
- Near／Next contracts
- Spot basis
- Continuous futures
- Institutional futures positions
- Top 5／Top 10 concentration
- TXO Put／Call ratio
- Strike open interest
- Max Pain
- Volatility domain boundary
- Market Overview derivatives summary
- Android Futures UI
- Room offline cache
- Stale／Unavailable UI states
- Backend and Android automated tests
- API 35 emulator instrumentation

## Software Completion

- Derivatives Domain：COMPLETE
- Database schema：COMPLETE
- Alembic migration：COMPLETE
- TAIFEX Provider abstraction：COMPLETE
- Official TAIFEX OpenAPI adapter：COMPLETE
- Deterministic Fake Provider：COMPLETE
- Futures API：COMPLETE
- Institutional Futures API：COMPLETE
- Put／Call API：COMPLETE
- Strike OI API：COMPLETE
- Max Pain calculation：COMPLETE
- Market Overview partial handling：COMPLETE
- Android Futures presentation：COMPLETE
- Cache and offline behavior：COMPLETE
- CI validation：COMPLETE

## Known External Data Constraints

### TWSE lending availability

- `lending_short_sell`：official OpenAPI supported
- `borrowed_shares`：unavailable
- `returned_shares`：unavailable
- `borrowing_balance`：unavailable
- `lending_short_balance`：unavailable
- Missing official fields remain `null`
- Missing official fields are never zero-filled
- Website-only datasets are not scraped
- Fake data never substitutes for a formal source
- External availability does not mark the Software Slice incomplete

### TAIWAN VIX licensing

- TAIFEX OpenAPI does not expose the required historical VIX API
- An official historical download service exists
- Automated download permission is unverified
- Storage permission is unverified
- App redistribution／reuse permission is unverified
- Current classification：`PUBLIC_DOWNLOAD_UNVERIFIED_REUSE`
- Formal Provider state：`UNAVAILABLE`／`LICENSE_REQUIRED`
- No HTML scraping or browser automation
- No Fake fallback in formal operation
- External licensing does not mark the Software Slice incomplete

## Data Integrity Rules

- Preserve upstream missing values as `null`
- Do not derive unavailable official lending values
- Do not use zero as an unavailable-data placeholder
- Keep official and Fake Providers separate
- Keep licensing policy in Provider configuration
- Treat unknown permissions as `null`
- Keep Market Overview available sections visible as `PARTIAL`
- Do not turn a single unavailable section into an HTTP 500 response

## Primary References

- `docs/13_PHASE_3_WATCHLIST.md`
- `docs/12_PHASE_3_PORTFOLIO_CORE.md`
- `docs/11_PHASE_2_DERIVATIVES.md`
- `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`
- `docs/04_DEVELOPMENT_ROADMAP.md`
- `api/openapi.yaml`
- `.github/workflows/ci.yml`

## Next Work Boundary

- Phase 2 is closed
- Phase 3 / Slice 1 is closed
- Phase 3 / Slice 2 is closed after GitHub CI success
- Next planned work is Phase 3 / Slice 3 — Alert Engine; implementation has not started
- Do not reopen Phase 2 solely for external licensing availability
- Future providers may replace unavailable sources through existing boundaries
- Any further Phase 3 work requires a separate explicit request and Slice definition
- Preserve `phase-2-slice-2-complete` as the Phase 2 release boundary
