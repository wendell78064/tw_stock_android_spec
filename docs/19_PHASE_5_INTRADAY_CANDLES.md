# 19 — Phase 5 / Slice 2: Intraday Quote + 1m/5m K

狀態：**COMPLETE**

Feature commit：`3517acf`

GitHub Actions：[Run 31680550147](https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31680550147)

- backend：**PASS**
- android：**PASS**
- android-instrumentation：**PASS**
- CI `connectedDebugAndroidTest`：**PASS**，API 35 x86_64 emulator 實際完成 25 tests（0 skipped、0 failed）
- Local device instrumentation execution：**NOT RUN**

## Semantics

- `1m` 依 `Asia/Taipei` 交易所時鐘切桶，內部與 API timestamp 使用 UTC。
- Decimal OHLC；第一筆有效 update 建立 OHLC，sequence duplicate、舊 sequence、舊 timestamp 不更新 close。
- cumulative volume/turnover 使用 delta。Reset 產生零 delta 與 STALE 診斷，不使用負值或 `abs()`。
- Snapshot 只更新 cumulative-volume baseline，支援 reconnect semantics 與 restart recovery，避免整日累積量灌入單根 K。
- 下一 bucket 到達時 finalize 前一根 1m candle；無成交分鐘不補造 candle。
- `5m` 僅由 1m candle 聚合，確保 OHLCV 一致；不同 session 永不合併。

## Redis and Recovery

- Current: `intraday:current:{interval}:{market}:{code}:{session}`。
- History: `intraday:candles:{interval}:{market}:{code}:{session}` sorted set，以 bucket timestamp 查詢與覆寫 active candle。
- Baseline: `intraday:baseline:{market}:{code}:{session}`，避免重啟或 reconnect 將全日 cumulative volume 灌入單根 K。
- Retention 集中設定為最近 5 個交易日目標（key TTL 7 日，涵蓋週末）；restart 從 current/baseline 安全恢復。
- PostgreSQL 與 Room schema 均未變更。
- Redis failure 限縮於 realtime pipeline；既有 EOD API 不依賴此 cache。

## Protocol and API

- `/v1/ws/quotes` protocol v1 保持 quote 相容，subscribe 可帶 `quote`, `candle_1m`, `candle_5m` channels。
- 訂閱 candle channel 先收到 initial `candle_snapshot`，後續收到 active/final `candle` updates；payload 含 `interval` 與 `is_final`。
- `GET /v1/intraday/{market}/{code}/candles` 支援 `interval`, `date`, `from`, `to`, `limit`，不掃描 Redis keys。

## Android 1D Chart

- Security Detail 的 `1D` 使用 intraday REST snapshot + WebSocket incremental updates，1m/5m 可切換。
- 使用既有 Compose Canvas candlestick/pan/touch selection，顯示 volume、OHLCV、as-of 與連線狀態。
- Active bucket 以 key 原位替換，新 bucket append；`followLatest=false` 時不強制回最右。
- Production provider 未配置時顯示「即時盤中行情尚未配置」；fake provider 僅供 dev/test/CI。

## Tests and Performance

- Backend deterministic tests涵蓋 OHLC、Decimal、volume delta/reset、ordering、finalization、5m、session/時區與 Redis overwrite/query。
- Android affected module compile、unit/UI suites與 500-candle Canvas 路徑納入 final validation。
- Performance smoke：100 securities × 1 quote/sec × 10 simulated minutes（60,000 quotes）於單機 Redis 完成 95.68s、627 quotes/sec、500 bounded keys、0 aggregation errors；無 duplicate history member。

## Limitations

- Production authorized realtime provider 仍為 `UNCONFIGURED`。
- Redis 僅為短期 operational store，未提供長期分鐘 K。
- 不包含 alerts、industry strength、FCM、cloud sync、AI 或 trading。
