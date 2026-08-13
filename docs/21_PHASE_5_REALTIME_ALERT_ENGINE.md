# 21 — Phase 5 / Slice 4: Realtime Alert Engine

狀態：**COMPLETE**

## EOD / Realtime Boundary

- `evaluation_mode` 明確分為 `EOD` 與 `REALTIME`；既有規則 migration default 為 EOD，原有 evaluation 行為不變。
- REALTIME 僅支援 REGULAR session 的 PRICE_TARGET/STOP/ADD、MA_NEAR/TOUCH/CROSS_ABOVE/CROSS_BELOW；close/consecutive 規則以 422 拒絕。
- Production Realtime Provider：`UNCONFIGURED`；Fake 僅供 dev/test/CI，不冒充正式來源。

## Crossing / Snapshot Semantics

- Price alert 使用 previous realtime price 到 current price 的 edge crossing，不以持續滿足條件重複觸發。
- 初始、重連 snapshot、restart 無 state、以及新交易日第一筆 quote 都只建立 baseline。
- 僅 LIVE、REGULAR、正序 UPDATE 可觸發；duplicate/older sequence 或 timestamp、STALE/UNAVAILABLE 不觸發。

## Intraday-updated Daily MA

- `dynamic_ma_n = (previous N-1 finalized daily closes sum + current realtime price) / N`，支援 MA5/10/20/60/120/240，全程 Decimal。
- 歷史 closes 在 rule refresh 時 bulk preload；每 tick O(1)，不足 N-1 筆時 MA unavailable，不縮短期間或補零。
- Cross 前後各自使用 previous/current dynamic MA；Near 採 outside → near edge entry；Touch tolerance 集中為 0.05%，也接受 relation crossing。此 MA 是盤中更新日線 MA，不是 1m/5m MA。

## State / Dedup / Delivery

- Redis key：`realtime:alert:state:{rule_id}:{security_id}`，TTL 48 小時，保存 price、dynamic MA、relation、sequence、timestamp、trade date 與 fingerprint。
- Fingerprint 包含 rule/security/event type 及 provider sequence（無 sequence 時使用 exchange timestamp），只阻擋 replay；合法第二次 crossing 仍形成 durable event。
- Cooldown 與 daily limit 僅抑制 notification eligibility，meaningful occurrence 仍寫 `alert_events`；event JSON metadata 保存 realtime timestamp/provider/sequence/reference/status。
- Alert WebSocket protocol v1 channel 為 `alert`，訊息為 `alert_event`；Android 不自行評估規則。

## Scope / Subscription

- SECURITY/PORTFOLIO/WATCHLIST 沿用既有 membership resolver；規則與 membership 每 60 秒 bounded refresh。
- subscription set 以 security 去重；同一股票多規則/多 scope 只形成一個 active security subscription。移除、賣光或 disable 後，下次 refresh 取消並清除對應 Redis state。

## API / Android

- Alert CRUD 增加 `evaluation_mode`、`session_scope`；`GET /v1/alerts/realtime/status` 回 provider、availability、active rules/subscriptions 與 last quote time。
- Android editor 顯示盤後/盤中即時模式，盤中只列支援條件；provider 未配置時保留設定並顯示 inactive 說明。
- Notification Center 顯示盤中 badge、成交價與客觀 dynamic MA reference；本機通知以 event fingerprint 去重。FCM：`UNCONFIGURED`，不影響本 Slice。

## Tests / Performance

- Backend：initial/reconnect/day baseline、price crossings、ordering/status、dynamic MA coverage/cross、dedup、cooldown/daily limit、EOD regression、Redis/WS protocol。
- Android：mode selector、supported filtering、provider banner、realtime badge、local notification fingerprint dedup、既有 ViewModel regression。
- Performance smoke：100 securities × 20 rules = 2,000 affected evaluations；100-security burst 32.779ms，平均 0.328ms/security quote。MA context/membership bulk cached、無 per-rule DB 或 per-quote history query。

## Final CI Validation

- GitHub Actions：[Run 31684839240](https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31684839240)
- backend：**PASS**
- android：**PASS**
- android-instrumentation：**PASS**
- GitHub device instrumentation：`:app:connectedDebugAndroidTest` **PASS**，API 35 emulator，25 tests，0 skipped，0 failed。
- Local device instrumentation execution：**NOT RUN**
- PostgreSQL `0011 → 0012 → 0011 → 0012` migration round-trip：**PASS**。

## Database / Limitations

- PostgreSQL migration：`0012_realtime_alert_engine`；Room 維持 version 10。
- Durable rules/events 存 PostgreSQL，transient relation state 存 Redis。
- 不包含 FCM remote push、Cloud Sync、AI、broker/auto trading、realtime screener/comparison automation。
- Phase 5 software implementation 已完成，但 production realtime 尚受 authorized/configured/available/redistribution license provider 與必要時 FCM 設定之外部條件限制；不得描述為 production realtime ready。
