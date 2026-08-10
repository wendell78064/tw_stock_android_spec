# Phase 1 / Slice 2 Hardening

## 技術指標參數模型

Android 以 `TechnicalIndicatorPreferences` 聚合 MA、EMA、MACD、RSI、KD、Bollinger、ATR 與 Williams %R 的型別化設定；OBV 沒有數值參數。設定頁使用 Material 3 對話框，由走勢頁的「指標設定」進入，不在 K 線畫面堆疊輸入欄位。

預設值為 MA 5/10/20/60/120/240、EMA 12/26、RSI 14、MACD 12/26/9、KD 9/3/3、Bollinger 20/2、ATR 14、Williams %R 14。所有 period 與平滑參數必須大於零，MA 不可重複，MACD slow 必須大於 fast，Bollinger 標準差倍數必須大於零。

## DataStore persistence

`IndicatorSettings` 將完整型別設定保存於 Preferences DataStore。支援儲存、取消、單一指標重設及全部重設。儲存後 Chart ViewModel 立即重新請求；離線時設定仍保存，畫面明確說明無法用新參數重新計算，舊快取不得冒充新結果。

## Backend default/custom 策略

未提供參數時，`GET /v1/securities/{code}/technicals` 延續讀取 `twml-technical-v1` persisted snapshot。提供任一自訂參數時，以既有日價 request-time calculation，回傳 `twml-technical-v1-request`、實際使用參數與 Decimal 字串，不新增 per-user snapshot，也不修改行情資料。

## Emulator CI

GitHub Actions `android-instrumentation` 使用 Ubuntu、KVM、API 35、Google APIs x86_64 AVD，關閉動畫後執行：

```bash
cd android-app
./gradlew connectedDebugAndroidTest
```

本機亦可在已啟動且 `adb devices` 可見的 emulator 上執行相同命令。

## 已知限制與授權邊界

自訂參數必須連線至 Backend 即時計算；離線僅保留原 K 線快取與 stale 提示。資料來源及授權仍遵循 `docs/05_DATA_SOURCES_AND_COMPLIANCE.md`，本切片沒有新增爬蟲或後續產品功能。
