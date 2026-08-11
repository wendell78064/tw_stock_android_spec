# Phase 2 / Slice 2：臺灣衍生品日資料

本 Slice 僅提供盤後日資料。支援 TX、MTX、TMF、TE、TF 與 TXO；不含即時、夜盤串流、分鐘 K、交易或投資組合功能。

## Provider 與官方來源

`OfficialTaifexProvider` 透過 TAIFEX OpenAPI 的期貨每日行情、三大法人期貨契約、十大交易人未平倉、Put/Call Ratio 與選擇權每日行情取得資料。URL 集中在 `TAIFEX_ENDPOINTS`；共用 client 提供 User-Agent、timeout、限速、retry/backoff 與 schema guard。官方中文欄位只存在 Adapter，缺值保持 `null`。

Carry-over 的 `OfficialTwseProvider`／`OfficialTpexProvider` 已正式接線市場指數、廣度、三大法人與信用資料；正式來源失敗不會 fallback Fake。TWSE 交易單位在 Adapter 明確換算為股。Fake provider 僅供固定測試。

TAIFEX OpenAPI 未提供目前系統所需的 TAIWAN VIX 歷史 API。官方網站另有歷史下載資料，但自動下載、保存及 App 再呈現／再利用須依授權狀態決定；目前分類為 `OFFICIAL_DOWNLOAD`／`PUBLIC_DOWNLOAD_UNVERIFIED_REUSE`，正式 ingestion 回傳 unavailable，不爬取網頁、不以假值替代。若取得授權資料，沿既有 provider boundary 接入。

## TWSE Lending Capability Matrix

| Domain capability | 正式來源分類 | 系統行為 |
|---|---|---|
| `borrowed_shares` | `UNAVAILABLE` | `null`，不由其他欄位推算 |
| `returned_shares` | `UNAVAILABLE` | `null`，不補零 |
| `borrowing_balance` | `UNAVAILABLE` | `null`，不以借券賣出量代替 |
| `lending_short_sell` | `OFFICIAL_OPENAPI` | 精確對應 TWSE「借券賣出股數」 |
| `lending_short_balance` | `UNAVAILABLE` | `null`，不使用 website-only scraper |

系統只自動接入允許的官方 API dataset；website-only dataset 不使用 scraping。TWSE lending provider policy 為 `OFFICIAL_OPENAPI`／`VERIFIED_OPEN_DATA`，其餘能力缺口是外部資料不可得，而非軟體尚未實作。

## TAIWAN VIX Source Capability

| 來源 | Capability | License status | 自動下載／保存／再呈現 |
|---|---|---|---|
| TAIFEX OpenAPI | `UNAVAILABLE` | `UNAVAILABLE` | 未提供所需歷史 API |
| TAIFEX 官方下載 | `OFFICIAL_DOWNLOAD` | `PUBLIC_DOWNLOAD_UNVERIFIED_REUSE` | `null`／`null`／`null`，待授權確認 |
| 授權 vendor | `LICENSED_VENDOR` | `VERIFIED_LICENSED` | 由 provider configuration 決定 |

API 在尚無已驗證正式資料時以 `data_status=UNAVAILABLE` 搭配 `license_status=PUBLIC_DOWNLOAD_UNVERIFIED_REUSE`，明確區分外部授權限制與 implementation incomplete。

## Licensing / Availability Classification

`source_type`、`source_capability`、`license_status`、`automation_allowed`、`storage_allowed`、`redistribution_allowed` 由 Provider policy 提供；布林值 `null` 表示尚未確認，不自動解讀為允許或禁止。法律／授權狀態不是不可變 Domain 事實，可在取得正式授權後替換設定與 Provider。

## External Data Limitations

正式流程不使用 HTML scraping、browser automation、private API、反向工程下載端點、Fake fallback 或 zero-fill。借券餘額與 VIX 不可用時，API 保留 `null`／`UNAVAILABLE`，Android 顯示來源不可用；Market Overview 的其他 section 可用時維持 `PARTIAL`，單一 section 不使整頁失敗。

## Phase 2 Slice 2 Completion Criteria

Software Gate 與 External Data Gate 分開驗收。外部資料的最終狀態允許為 `SUPPORTED`、`UNAVAILABLE` 或 `LICENSE_REQUIRED`；只要分類真實、API 與 Android 不誤導、無未授權擷取或替代資料，且 provider 可替換，即視為 Software Slice 完成。封版仍須以本次 local validation 與 GitHub emulator CI 實際通過為前提。

## 商品、契約與行情

`futures_products` 保存商品與乘數，`futures_contracts` 使用商品 namespace 加實際年月契約碼，並保存到期日、最後交易日與狀態。Near／Next 依仍有效契約月份排序，不把近月符號當永久商品。

`futures_daily_prices` 保存 regular/after-hours session 的 OHLC、結算價、成交量與總未平倉。基差定義為「期貨收盤／結算價減現貨 TAIEX 收盤」。所有價格與金額用 Decimal。

Continuous Futures 支援 `VOLUME`、`OPEN_INTEREST`、`EXPIRY` roll。回應逐點揭示 `source_contract`、`roll_date`、`roll_method`、`adjustment_method=NONE` 與 `twml-continuous-v1`；本版不做價差回補調整。

## 法人、集中度與選擇權風險

法人期貨保存買賣口數、金額、未平倉與前一交易日變化；查詢視窗為 1/5/10/20/60 日。金額由官方仟元換算為元。集中度保存 Top 5/10 多空 OI 與占市場總 OI 比例。

TXO 保存成交量與 OI Put/Call Ratio、Call/Put 各履約價 OI。Max Pain 對候選履約價計算到期總內含價值損失，回傳最小值、並列履約價與 `twml-max-pain-v1`；資料不足回傳 unavailable，不補零。

VIX percentile 以查詢視窗內「小於等於最新值」的觀測比例計算，屬 derived data，原始 VIX 行情不被修改。

## Database 與 ingestion

Alembic `0005_derivatives_market` 建立 products、contracts、daily prices、institution positions、concentration、put/call、strike OI、volatility 與 continuous metadata 表及索引。每個 dataset 有獨立 ingestion run、checksum、source/as-of/received-at/status/revision；重跑相同 fixture 冪等。

```bash
make sync-derivatives PROVIDER=fake DATE=2026-08-07
make sync-futures PROVIDER=taifex DATE=2026-08-07
make sync-futures-institutional PROVIDER=taifex DATE=2026-08-07
make sync-options PROVIDER=taifex DATE=2026-08-07
make sync-market-spot PROVIDER=twse DATE=2026-08-07
make sync-market-spot PROVIDER=tpex DATE=2026-08-07
```

## API

主要入口為 `/v1/futures/products`、product overview/contracts/continuous/open-interest/institutional/concentration、TXO put-call/strike/max-pain 與 `/v1/market/volatility`。`/v1/market/overview` 同時回傳 TX、法人期貨與衍生風險摘要。完整參數以 `api/openapi.yaml` 為準。

## Android、快取與 Offline

市場首頁顯示 TX 近月摘要並可開啟 Futures Detail。Detail 支援區間與三種轉倉策略，顯示近月／次月、基差、連續序列及法人 OI。DTO 先轉 Domain，UI 使用 immutable state。Room v4 保存最後成功的期貨 overview；離線時明示 Stale，未快取或上游缺資料顯示 unavailable，不用舊數值冒充新資料。

## 測試、效能與限制

Backend fixture 測試涵蓋 mapping、schema guard、ingestion 冪等、契約、視窗、三種 roll、Max Pain tie/missing 與 Decimal。Android 測試涵蓋 repository、ViewModel state 與 Compose。常用查詢具有商品、契約、交易日索引，發布前以 `EXPLAIN ANALYZE` 確認。

只使用 TWSE、TPEx、TAIFEX 官方允許存取介面；不使用未授權爬蟲，也不重散布未取得權利的指數歷史。官方修訂與缺漏會反映 metadata/status。本 Slice 沒有即時／夜盤串流、分鐘 K、完整 option chain UI 或授權 VIX 歷史。

## 驗證紀錄

2026-08-10 驗證結果：Backend Ruff 與 32 項 Pytest、Docker image、OpenAPI validation／Kotlin generation、Android lint／unit tests／Debug APK／instrumentation APK、Alembic downgrade/upgrade、PostgreSQL／Redis／Backend health、60+ 交易日 Fake backfill、API smoke 與索引查詢計畫均通過。

GitHub Actions API 35 x86_64 emulator 的 `connectedDebugAndroidTest` 已通過；run #6：<https://github.com/wendell78064/tw_stock_android_spec/actions/runs/31354579169>。

### Phase 2／Slice 2 Final CI

GitHub Actions（commit `217b3b7`）結果：**PASS**。

```text
backend: PASS
android: PASS
android-instrumentation: PASS

Android Emulator:
API 35
Google APIs
x86_64
```

Phase 2／Slice 2 Software Gate 與 CI Gate 已全部通過。外部資料 Gate 已分類：TAIFEX OpenAPI 未提供所需 VIX 歷史 API，官方下載的再利用權限尚未確認；TWSE OpenAPI 的「借券賣出股數」只映射為 `lending_short_sell`，不冒充借券成交或餘額。兩者均未使用爬蟲、Fake fallback 或 zero-fill，屬 external data availability，不再標記為 software incomplete。
