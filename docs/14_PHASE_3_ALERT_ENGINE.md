# Phase 3 / Slice 3：Alert Engine

## Rule and Scope Model

Rule types：`PRICE_TARGET`、`PRICE_STOP`、`PRICE_ADD`、`MA_NEAR`、`MA_TOUCH`、`MA_CROSS_ABOVE/BELOW`、`MA_CLOSE_ABOVE/BELOW`、`MA_CONSECUTIVE_ABOVE/BELOW`。MA periods 為 5／10／20／60／120／240。Scope 支援 SECURITY、PORTFOLIO、WATCHLIST；後兩者每次 evaluation 動態解析目前持股／item，不保存 security snapshot。

## Price Conditions

Target 為 previous close `< threshold` 且 current close `>= threshold`。Stop 與 Add 均定義為 previous close `> threshold` 且 current close `<= threshold`；Add 是使用者設定的回落價，不代表系統建議。

## MA Definitions

- Near：`abs(close-ma)/ma*100 <= threshold_percent`，集中預設 1%，範圍 `(0,20]`。
- Touch：Daily low/high range intersects MA，即 `low <= MA <= high`。
- Cross：比較前一有效交易日 close/MA 與本日 close/MA。
- Close：本日 close 高於／低於 MA；由 dedup/cooldown 防止重跑通知。
- Consecutive：只使用有效交易日資料，N 範圍 2～60。

## Evaluation Engine

`AlertEvaluationService` 批次解析 enabled rules、dynamic membership、所需 daily prices 與 technical snapshots，再由 evaluator strategy 計算客觀 occurrence。FINAL 正常評估；STALE 可觸發且 event 保留 STALE；PARTIAL 僅在必要欄位完整時評估；UNAVAILABLE、missing MA 或 cross 缺 previous day 均不觸發。

## Dedup, Cooldown, Daily Limit

Fingerprint 是 `SHA256(rule_id:security_id:trade_date:event_type)`，DB unique constraint 保證 idempotency。Cooldown 預設 1440 minutes。每 rule daily notification limit 預設 5；所有 occurrence 仍保存 event history，只有 `notification_eligible` 受限制。

## Audit and Notification Center

`alert_evaluation_runs` 記錄 target date、開始／完成時間、rules、securities、events、errors 與 status。`alert_events` 同時是 event history 與 Notification Center single source of truth，支援 unread filter、mark read、read all。

## Android and Offline

`feature-alert` 提供 Rules、Create/Edit 與 Notification Center；Portfolio Holding、Watchlist Item 與 Security Detail 均提供明確建立入口，Watchlist 已設定價格只作表單 prefill，不會 silent create。Room version 7 以 explicit `6 → 7` migration 快取 rules/events。離線僅允許讀 cache，Backend authoritative writes 不建立 offline queue。UI 只顯示客觀描述。

## FCM Boundary

`NotificationDeliveryProvider` 保留 Local 與 Future FCM boundary；沒有 Firebase credentials 時 FCM 為 `UNCONFIGURED`，Notification Center 不依賴 FCM。

## Tests and Performance

Final local validation：Ruff PASS；Pytest 80 passed；OpenAPI validation／Kotlin client generation PASS；Android lint／unit／Debug APK／Instrumentation APK PASS；Alembic `0007 → 0008 → 0007 → 0008` PASS。測試涵蓋 price/MA semantics、missing/stale/partial、validation、dynamic membership、dedup、daily limit、audit、API CRUD、Notification Center、Android rules/create/notification/offline states 與 deterministic instrumentation fixture。50 securities × 20 rules deterministic smoke 為 8.068 ms，membership／market／event-state 各一次 bulk call。

## Limitations

- Daily/latest available data only；不含 realtime、minute K、WebSocket
- 不含 remote FCM setup、Cloud Sync、Broker／automatic trading
- 不含 Industry／Theme、Screener、Comparison 或 AI recommendation
