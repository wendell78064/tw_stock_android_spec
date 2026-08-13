# 20 — Phase 5 / Slice 3: Realtime Market / Industry Strength

狀態：**IMPLEMENTED — WAITING FOR CI**

## Market Realtime Snapshot

- TWSE/TPEx 分開聚合；`last_price` 對可靠 `previous_close` 定義 advancer/decliner/unchanged。
- 缺 previous close 的股票排除 breadth denominator，不視為平盤。
- 回傳 total/valid/quoted members、coverage、advance/decline ratio、turnover availability、live/stale/unavailable count。
- 不合成或捏造 TAIEX/OTC realtime index price；正式 provider 未配置時不標示 production LIVE。

## Taxonomy Aggregation

- Industry/Theme membership 由既有 SQL tables 一次 bulk load 為 immutable process snapshot；每 quote 無 SQL lookup。
- Quote 只更新該 market、industry 與 overlapping themes；membership 下次 reload 即反映變更。
- Equal-weight return 為有效 member 的 `last / previous_close - 1` 平均；缺資料不補 0。
- Leaders/laggards 依 realtime return deterministic 排序。

## Realtime Strength

- Algorithm：`twml-industry-realtime-strength-v1`，與 EOD `twml-industry-strength-v1` 完全分離。
- Momentum 35%、Breadth 30%、Technical Participation 25%、Turnover 10%。
- 同一 taxonomy type/as-of 使用 deterministic percentile（tie 採平均 rank）後加權。
- 缺 component 不給 0，剩餘權重正規化；component coverage < 60% 時 score/rank 為 null。
- Technical 欄位明確表示 realtime price vs persisted EOD MA20/MA60，並非 intraday 重算 MA；資料不可用即 null。
- Institutional EOD prior 未納入 realtime score，不冒充盤中法人流。

## Redis / WebSocket / HTTP

- Keys：`realtime:market:*`、`realtime:taxonomy:{industry|theme}:*`、`realtime:ranking:*`，TTL 120 秒。
- Pub/Sub：`realtime:market`、`realtime:industry-strength`、`realtime:theme-strength`。
- Protocol v1 新增 `market`、`industry_strength`、`theme_strength` channels；quote/1m/5m candle 相容。
- Subscribe 先收到 market/ranking snapshot，再接 market/taxonomy updates。
- Ranking publish 以集中設定的 250ms interval throttle；受影響 taxonomy snapshot 仍逐次更新。
- REST：realtime markets、industry/theme rankings 與 detail；支援 strength/return/breadth/turnover sort。

## Android

- Market Home 顯示盤中 breadth、coverage、status 與 as-of；既有 EOD index 保持不變。
- Industry Landing 明確區分盤中與盤後算法，支援 industry/theme ranking。
- 排名列顯示 score、rank、return、advance ratio、MA20 availability、coverage/status 與 component breakdown。
- WebSocket event 以 500ms debounce 觸發 REST snapshot refresh；disconnect 保留最後 snapshot 並標 STALE。

## Tests / Performance

- Backend tests：breadth、coverage、market separation、overlap membership、partial、leaders、percentile tie、Redis/WS initial snapshots、protocol compatibility。
- Android tests：initial snapshot、disconnect stale、market breadth、industry realtime ranking/components。
- Performance smoke：1000 securities / 50 taxonomies / 10,000 memberships / 100 quotes，平均 2.024ms/quote；membership 為 process snapshot、Redis writes 僅限 market 與 affected taxonomies，ranking burst publish 由 250ms throttle 限制，in-memory quote state bounded by 1000-member universe。

## Database / Limitations

- PostgreSQL head 維持 `0011_stock_screener`；Room version 維持 9。
- Realtime state 僅存 Redis；EOD strength DB 不變。
- Production Realtime Provider：`UNCONFIGURED`；fake 僅供 dev/test/CI。
- 不包含 realtime alerts、screener execution、comparison、FCM、Cloud Sync、AI 或 trading。
