# Phase 3 / Slice 2：Watchlist Core

## Architecture

Watchlist group 與 item settings 由 Backend authoritative ledger 保存；市場資料不複製到 item。`WatchlistService` 負責 CRUD、驗證、batch reorder 與 overview enrichment，Controller 只處理 transport mapping。

## Database

Alembic `0007_watchlist_core` 建立 `watchlists` 與 `watchlist_items`。同一 security 可存在多群組；群組內 `(watchlist_id, security_id)` 唯一。item 隨群組 cascade delete，security 與市場資料不受影響。Target／stop／add price 使用 `NUMERIC(24,8)`、允許 null 且非 null 時大於 0。

## API

提供群組與 item CRUD、`PUT /v1/watchlists/reorder`、`PUT /v1/watchlists/{id}/items/reorder` 及 `GET /v1/watchlists/{id}/overview`。Security resolution 沿用 Security domain；重複加入回 conflict。價格設定以 Decimal string 傳輸。

## Group and Item Model

支援多群組、群組與 item manual order、500 字內 note，以及中性的 target／stop／add price settings。這些欄位只保存設定，不觸發 alerts 或投資建議。

## Market Enrichment

Overview 以單一 bulk SQL 查詢 latest daily close/change、MA5／MA20／MA60／RSI14、最新法人與信用摘要。缺資料保持 null，整列標示 `PARTIAL`／`UNAVAILABLE`；行情為 latest available daily price，並回傳日期，不是 realtime。

## Android

`feature-watchlist` 啟用「自選」bottom navigation，提供群組切換與 CRUD、加入／移除股票、設定編輯、Move Up／Down manual reorder，以及 Manual／Code／Change %／Foreign net view sort。View sort 不修改 persisted manual order。

## Offline

Room version 6 新增 watchlist group/item overview cache，使用明確 `5 → 6` migration。離線只允許讀取 cache 並顯示 `OFFLINE · STALE` 與 `price_as_of`；所有寫入仍需 Backend 成功，不建立 offline write queue。

## Performance

50-security deterministic smoke 驗證一次 repository bulk call；關鍵 overview query 使用 group/order 與 security indexes，避免逐檔 Service/API N+1。

## Tests

Backend 涵蓋 group/item CRUD、duplicate、跨群組、settings validation、batch reorder、security errors、status、bulk call、50-security 與 API smoke。Android 涵蓋 ViewModel mutations/group switching/sort、Empty／Partial／Offline Compose states與 deterministic instrumentation fixture。Final validation 另記錄 Ruff、Pytest、OpenAPI、client generation、lint、unit、APK、Room compile 與 Alembic round-trip。

Final local validation：

- Ruff：PASS
- Pytest：59 passed
- OpenAPI validation／Kotlin client generation：PASS
- Android lint／unit tests：PASS
- Debug APK／Instrumentation APK：PASS
- Room version 5 → 6 explicit migration compile validation：PASS
- Alembic `0006 → 0007 → 0006 → 0007`：PASS
- Watchlist API smoke：PASS
- 50-security bulk overview：PASS（55.04 ms）
- Critical item query `EXPLAIN ANALYZE`：index scan，0.125 ms
- Official Provider smoke：NOT RUN

## Limitations

- 不含 Alert Engine、MA／Price alerts、push／Notification Center
- 不含 realtime、WebSocket、minute K
- 不含 Industry／Theme、Screener、Comparison、Cloud Sync、CSV 或 AI
- 法人與信用缺資料不補 0；TWSE lending availability 維持既有 Provider capability
