from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.analysis_snapshot import (
    PriceSnapshot,
    PromptSectionStatus,
    ReturnsSnapshot,
    SecurityAnalysisSnapshot,
)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _fmt_dec(val: Decimal | float | None, suffix: str = "", default: str = "NULL") -> str:
    if val is None:
        return default
    if isinstance(val, Decimal):
        val_float = float(val)
        if abs(val_float) >= 1000:
            formatted = f"{val_float:,.2f}"
        else:
            formatted = f"{val_float:.2f}"
        return f"{formatted}{suffix}"
    return f"{val}{suffix}"


def _fmt_int(val: int | None, suffix: str = "", default: str = "NULL") -> str:
    if val is None:
        return default
    return f"{val:,}{suffix}"


def _fmt_pct(val: Decimal | float | None, default: str = "NULL") -> str:
    if val is None:
        return default
    val_float = float(val)
    sign = "+" if val_float > 0 else ""
    return f"{sign}{val_float:.2f}%"


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "NULL"
    local_dt = (
        dt.astimezone(TAIPEI_TZ)
        if dt.tzinfo
        else dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(TAIPEI_TZ)
    )
    return local_dt.strftime("%Y-%m-%d %H:%M:%S CST")


class IndividualAnalysisPromptBuilder:
    """Builds a structured, bounded Traditional Chinese AI prompt from SecurityAnalysisSnapshot."""

    def build_prompt(self, snapshot: SecurityAnalysisSnapshot) -> str:
        sec = snapshot.security
        p: PriceSnapshot | None = snapshot.price
        r: ReturnsSnapshot = snapshot.returns
        tech = snapshot.technicals
        inst = snapshot.institutional
        credit = snapshot.credit
        ind = snapshot.industry
        mkt = snapshot.market_context
        deriv = snapshot.derivatives_context
        pos = snapshot.portfolio_position
        dq = snapshot.data_quality

        mkt_name = (
            "臺灣證券交易所 (上市 TWSE)"
            if sec.market.value == "TWSE"
            else "證券櫃檯買賣中心 (上櫃 TPEX)"
        )
        listing_str = sec.listing_date.isoformat() if sec.listing_date else "未提供"

        lines = [
            "【TW Market Ledger 智慧台股量化分析 Prompt】",
            "",
            "【重要分析指引】",
            "1. 以下量化數據由 TW Market Ledger 系統直接提供，請以此作為客觀分析之基礎事實。",
            "2. 數據中標示「NULL」、「UNAVAILABLE」或「STALE」者，"
            "代表資料未發布、不適用或尚未更新，嚴禁自行將其視為 0 進行計算或推論。",
            "3. 若您具備聯網或外部知識檢索能力，可主動查詢最新公開資訊"
            "（如重大新聞、法說會焦點、營收財報、產業動態或公司公告），但在分析回覆中必須明確區分：",
            "   (A) [TWML 數據]：基於本 Prompt 所提供之量化數據；",
            "   (B) [外部檢索]：由 AI 聯網或外部知識庫補充之資訊。",
            "4. 請保持客觀、專業、嚴謹之研究員口吻，切勿給出確定性保證報酬之承諾。",
            "",
            "=" * 60,
            "一、分析標的基本資料",
            f"• 股票名稱與代號：{sec.name} ({sec.code})",
            f"• 所屬市場：{mkt_name}",
            f"• 證券類別：{sec.security_type}",
            f"• 主要產業：{sec.primary_industry or '未提供'}",
            f"• 所屬題材：{', '.join(sec.themes) if sec.themes else '無'}",
            f"• 掛牌日期：{listing_str}",
            "",
            "二、資料基準時間",
            f"• 行情基準時間 (As Of)：{_fmt_dt(snapshot.as_of)}",
            f"• Snapshot 產生時間：{_fmt_dt(snapshot.generated_at)}",
            f"• 整體資料品質狀態：{dq.overall_status.value} "
            f"(完整度: {_fmt_dec(dq.completeness_pct, '%')})",
            "",
            "三、價格與歷史報酬",
        ]

        if p and p.close is not None:
            vol_lots = (
                _fmt_dec(Decimal(p.volume_shares or 0) / Decimal(1000), " 張")
            )
            turn_yi = (
                _fmt_dec((p.turnover_amount or Decimal(0)) / Decimal(100000000), " 億元")
            )
            lines.extend([
                f"• 最新收盤價 (RAW)：{_fmt_dec(p.close, ' 元')} "
                f"(開: {_fmt_dec(p.open)} / 高: {_fmt_dec(p.high)} / 低: {_fmt_dec(p.low)})",
                f"• 成交量：{_fmt_int(p.volume_shares, ' 股')} (約 {vol_lots})",
                f"• 成交金額：{_fmt_dec(p.turnover_amount, ' 元')} (約 {turn_yi})",
                "• 區間報酬率：",
                f"  - 1日 (1D)：{_fmt_pct(r.return_1d)}",
                f"  - 5日 (5D)：{_fmt_pct(r.return_5d)}",
                f"  - 10日 (10D)：{_fmt_pct(r.return_10d)}",
                f"  - 30日 (30D)：{_fmt_pct(r.return_30d)}",
                f"  - 1年 (1Y)：{_fmt_pct(r.return_1y)}",
            ])
        else:
            lines.append("• 價格與報酬數據：UNAVAILABLE / 無有效日 K 資料")

        lines.extend([
            "",
            "四、技術指標分析 (Technical Indicators)",
        ])
        if tech and tech.data_status != PromptSectionStatus.NO_DATA:
            lines.extend([
                "• 均線架構 (Moving Averages)：",
                f"  - MA5: {_fmt_dec(tech.ma5)} | MA10: {_fmt_dec(tech.ma10)} | "
                f"MA20 (月線): {_fmt_dec(tech.ma20)}",
                f"  - MA60 (季線): {_fmt_dec(tech.ma60)} | "
                f"MA120 (半年線): {_fmt_dec(tech.ma120)} | "
                f"MA240 (年線): {_fmt_dec(tech.ma240)}",
                "• 動能與擺盪指標：",
                f"  - RSI (14): {_fmt_dec(tech.rsi)}",
                f"  - KD (9,3,3): K = {_fmt_dec(tech.kd_k)} / D = {_fmt_dec(tech.kd_d)}",
                f"  - MACD (12,26,9): DIF = {_fmt_dec(tech.macd)} / "
                f"Signal = {_fmt_dec(tech.macd_signal)} / Hist = {_fmt_dec(tech.macd_hist)}",
                f"  - Williams %R (14): {_fmt_dec(tech.williams_r)}",
                "• 通道與波動度指標：",
                f"  - 布林通道 (20,2.0): 上軌 = {_fmt_dec(tech.bollinger_upper)} / "
                f"中軌 = {_fmt_dec(tech.bollinger_middle)} / "
                f"下軌 = {_fmt_dec(tech.bollinger_lower)}",
                f"  - ATR (14): {_fmt_dec(tech.atr)}",
                f"  - OBV (能量潮): {_fmt_dec(tech.obv)}",
            ])
        else:
            lines.append("• 技術指標數據：UNAVAILABLE / 尚未計算快照")

        lines.extend([
            "",
            "五、三大法人籌碼動向 (Institutional Trading)",
        ])
        if inst and inst.data_status != PromptSectionStatus.NO_DATA:
            f1 = _fmt_dec(Decimal(inst.latest_day.foreign_net_shares or 0) / 1000)
            t1 = _fmt_dec(Decimal(inst.latest_day.trust_net_shares or 0) / 1000)
            d1 = _fmt_dec(Decimal(inst.latest_day.dealer_net_shares or 0) / 1000)
            tot1 = _fmt_dec(Decimal(inst.latest_day.total_net_shares or 0) / 1000)

            f5 = _fmt_dec(Decimal(inst.cum_5d.foreign_net_shares or 0) / 1000)
            t5 = _fmt_dec(Decimal(inst.cum_5d.trust_net_shares or 0) / 1000)
            d5 = _fmt_dec(Decimal(inst.cum_5d.dealer_net_shares or 0) / 1000)
            tot5 = _fmt_dec(Decimal(inst.cum_5d.total_net_shares or 0) / 1000)

            f10 = _fmt_dec(Decimal(inst.cum_10d.foreign_net_shares or 0) / 1000)
            t10 = _fmt_dec(Decimal(inst.cum_10d.trust_net_shares or 0) / 1000)
            d10 = _fmt_dec(Decimal(inst.cum_10d.dealer_net_shares or 0) / 1000)
            tot10 = _fmt_dec(Decimal(inst.cum_10d.total_net_shares or 0) / 1000)

            lines.extend([
                f"• 單日買賣超 (張)：外資 {f1} | 投信 {t1} | 自營商 {d1} | 合計 {tot1}",
                f"• 5日累計買賣超 (張)：外資 {f5} | 投信 {t5} | 自營商 {d5} | 合計 {tot5}",
                f"• 10日累計買賣超 (張)：外資 {f10} | 投信 {t10} | 自營商 {d10} | 合計 {tot10}",
                f"• 連續買賣方向：外資連續 {_fmt_int(inst.consecutive_foreign_days, ' 日')} | "
                f"投信連續 {_fmt_int(inst.consecutive_trust_days, ' 日')}",
            ])
        else:
            lines.append("• 三大法人數據：UNAVAILABLE / 暫無資料")

        lines.extend([
            "",
            "六、信用交易與借券 (Margin, Short & Lending)",
        ])
        if credit and credit.data_status != PromptSectionStatus.NO_DATA:
            lines.extend([
                f"• 融資餘額：{_fmt_int(credit.margin_balance, ' 張')} "
                f"(單日增減: {_fmt_int(credit.margin_change, ' 張')})",
                f"• 融券餘額：{_fmt_int(credit.short_balance, ' 張')} "
                f"(單日增減: {_fmt_int(credit.short_change, ' 張')})",
                f"• 券資比：{_fmt_dec(credit.short_margin_ratio, '%')}",
                f"• 借券賣出餘額：{_fmt_int(credit.lending_balance, ' 股')} "
                f"(單日增減: {_fmt_int(credit.lending_change, ' 股')})",
            ])
        else:
            lines.append("• 信用交易與借券數據：UNAVAILABLE / 暫無資料")

        lines.extend([
            "",
            "七、產業與題材環境 (Industry & Theme Context)",
        ])
        if ind and ind.data_status != PromptSectionStatus.NO_DATA and ind.industry_name:
            rep_str = (
                f" (代表個股: {', '.join(ind.representative_stocks)})"
                if ind.representative_stocks
                else ""
            )
            rk_str = (
                f"第 {ind.rank or 'NULL'} 名 / 共 {ind.total_industries or 'NULL'} 個產業 "
                f"(強弱分數: {_fmt_dec(ind.strength_score)})"
            )
            lines.extend([
                f"• 所屬產業：{ind.industry_name}",
                f"• 產業強弱度排名：{rk_str}{rep_str}",
            ])
        else:
            lines.append("• 產業強弱指標：UNAVAILABLE / 暫無產業強弱快照")

        lines.extend([
            "",
            "八、大盤市場環境 (Market Context)",
        ])
        if mkt and mkt.data_status != PromptSectionStatus.NO_DATA:
            inst_spot_yi = (
                _fmt_dec((mkt.institutional_spot_net or Decimal(0)) / Decimal(100000000), " 億元")
                if mkt.institutional_spot_net is not None
                else "NULL"
            )
            lines.extend([
                f"• 加權指數 (TAIEX)：{_fmt_dec(mkt.taiex_close, ' 點')} "
                f"(漲跌幅: {_fmt_pct(mkt.taiex_change_pct)})",
                f"• 市場漲跌家數：上漲 {mkt.advances_count or 'NULL'} 家 | "
                f"下跌 {mkt.declines_count or 'NULL'} 家 | 平盤 {mkt.unchanged_count or 'NULL'} 家",
                f"• 全市場三大法人現貨買賣超：{inst_spot_yi}",
            ])
        else:
            lines.append("• 大盤市場數據：UNAVAILABLE / 暫無資料")

        lines.extend([
            "",
            "九、衍生品與市場情緒 Context (Derivatives & Sentiment)",
        ])
        if deriv and deriv.data_status != PromptSectionStatus.NO_DATA:
            lines.extend([
                f"• 台指期貨收盤價：{_fmt_dec(deriv.tx_close, ' 點')}",
                f"• 外資台指期未平倉淨部位 (Net OI)："
                f"{_fmt_int(deriv.foreign_futures_net_oi, ' 口')}",
                f"• 臺指選擇權 Put/Call Ratio：{_fmt_dec(deriv.option_put_call_ratio, '%')}",
                f"• 前十大特定交易人期貨集中度："
                f"{_fmt_dec(deriv.top10_trader_concentration_pct, '%')}",
                f"• 波動率指數 (VIX)：{deriv.vix_status} "
                "(TAIFEX VIX 公開 OpenAPI 暫未提供，維持 UNAVAILABLE 標註)",
            ])
        else:
            lines.append("• 衍生品數據：UNAVAILABLE / 暫無資料")

        lines.extend([
            "",
            "十、我的投資組合持股現況 (My Portfolio Position)",
        ])
        if pos:
            pos_lots = _fmt_dec(Decimal(pos.shares) / Decimal(1000), " 張")
            lines.extend([
                "• 持股狀態：【已持有】",
                f"• 持有股數：{_fmt_int(pos.shares, ' 股')} (約 {pos_lots})",
                f"• 移動平均成本：{_fmt_dec(pos.moving_average_cost, ' 元')}",
                f"• 最新市值：{_fmt_dec(pos.latest_market_value, ' 元')}",
                f"• 未實現損益：{_fmt_dec(pos.unrealized_pnl, ' 元')} "
                f"({_fmt_pct(pos.unrealized_pnl_pct)})",
            ])
        else:
            lines.append("• 持股狀態：【未持有 / 觀察名單標的】")

        lines.extend([
            "",
            "十一、資料品質與限制提示",
            f"• 資料狀態總結：{dq.overall_status.value}",
        ])
        if dq.freshness_notes:
            for note in dq.freshness_notes:
                lines.append(f"  - 註記：{note}")
        else:
            lines.append("  - 註記：核心量化資料已成功由 TW Market Ledger 最新盤後快照對齊。")

        lines.extend([
            "",
            "=" * 60,
            "【請外部 AI 針對上述標的進行深入分析並回答以下 12 項問題】",
            "",
            "1. 【股價趨勢與型態】：分析目前股價在短、中、長期均線架構中的"
            "多空排列型態與關鍵趨勢走向。",
            "2. 【技術指標綜合判讀】：整合 RSI、KD、MACD、布林通道與成交量，"
            "評估動能、超買/超賣與背離訊號。",
            "3. 【籌碼面力量】：剖析外資、投信與自營商在近 1D、5D、10D 的"
            "買賣超方向、集中度與連續性力道。",
            "4. 【信用交易與借券壓力】：分析融資餘額、融券增減、券資比與借券賣出變化，"
            "評估浮額與軋空/多殺多風險。",
            "5. 【產業強弱與族群效應】：結合所屬產業強弱度排名與題材趨勢，"
            "分析該股在產業族群中的相對位階。",
            "6. 【基本面與最新營運綜述】（可輔以外部檢索）："
            "結合近月營收動能、最新財報獲利表現或重大公告進行摘要。",
            "7. 【估值位階與市場預期】：檢視該股目前的評價水準（如本益比、殖利率區間），"
            "評估當前股價是否處於合理區間。",
            "8. 【潛在利多催化劑 (Bullish Catalysts)】："
            "條列未來 1~6 個月內可能推升股價進一步走強的關鍵動能。",
            "9. 【潛在風險與逆風因子 (Risk Factors)】："
            "條列該標的面臨的總經、產業競爭、毛利下滑或技術面破位等下行風險。",
            "10. 【關鍵支撐與壓力區間】：給出明確之短線支撐價位、長線防守價位，"
            "以及上方潛在之成交密集套牢壓力區間。",
            "11. 【未來 1~3 個月情境劇本推演】：",
            "    - 樂觀情境 (Bull Case)：觸發條件與目標空間",
            "    - 基準情境 (Base Case)：最可能的盤整或溫和走勢",
            "    - 悲觀情境 (Bear Case)：下行風險與防守關卡",
            "12. 【具體操作策略與風控指引】：",
        ])

        if pos:
            lines.extend([
                "    - 針對目前持有之部位（平均成本與損益如第十節），請提供：",
                "      (a) 續抱與順勢加碼之確認條件；",
                "      (b) 獲利減碼或逢高調節之觀察點；",
                "      (c) 明確之移動停損防守價位與風控防線。",
            ])
        else:
            lines.extend([
                "    - 針對尚未持有之觀望投資人，請提供：",
                "      (a) 較佳之進場佈局觀察時機與確認訊號；",
                "      (b) 追高之風險警戒線；",
                "      (c) 試單進場後之嚴格停損停利風控設定。",
            ])

        lines.extend([
            "",
            "※ 請依序結構化輸出，給予清晰、量化佐證且條理分明之完整分析報告。※",
        ])

        return "\n".join(lines)
