from decimal import Decimal

from app.domain.analysis_snapshot import (
    ComparisonAnalysisSnapshot,
    PromptSectionStatus,
)
from app.services.individual_prompt_builder import (
    _fmt_dec,
    _fmt_dt,
    _fmt_int,
    _fmt_pct,
)


class ComparisonAnalysisPromptBuilder:
    """Builds a structured, bounded Traditional Chinese AI prompt for comparing 2~5 securities."""

    def build_prompt(self, comparison_snapshot: ComparisonAnalysisSnapshot) -> str:
        snapshots = comparison_snapshot.snapshots
        mkt = comparison_snapshot.unified_market_context
        deriv = comparison_snapshot.unified_derivatives_context

        sec_names = [f"{s.security.name}({s.security.code})" for s in snapshots]
        sec_header_str = " vs ".join(sec_names)

        lines = [
            "【TW Market Ledger 智慧台股多個股比較分析 Prompt】",
            "",
            "【重要分析指引】",
            (
                "1. 以下量化數據由 TW Market Ledger 系統直接提供，"
                "請以此作為客觀橫向對比分析之基礎事實。"
            ),
            (
                "2. 各股票行情與指標可能有不同之基準時間 (As Of) 與品質狀態，"
                "請注意對齊基準。"
            ),
            (
                "3. 數據中標示「NULL」、「UNAVAILABLE」或「STALE」者，"
                "代表資料未發布、不適用或尚未更新，嚴禁自行將其視為 0 進行計算或推論。"
            ),
            (
                "4. 若您具備聯網或外部知識檢索能力，可主動查詢最新公開資訊"
                "（如新聞、法說會、財報營收、產業動態或公司公告），但在分析回覆中必須明確區分："
            ),
            "   (A) [TWML 數據]：基於本 Prompt 所提供之量化數據；",
            "   (B) [外部檢索]：由 AI 聯網或外部知識庫補充之資訊。",
            "5. 請保持客觀、專業、嚴謹之研究員口吻，切勿給出確定性保證報酬之承諾。",
            "",
            "=" * 60,
            f"一、比較標的基本資料 ({sec_header_str})",
        ]

        for idx, s in enumerate(snapshots, 1):
            sec = s.security
            mkt_str = "上市 TWSE" if sec.market.value == "TWSE" else "上櫃 TPEX"
            theme_str = ", ".join(sec.themes) if sec.themes else "無"
            listing_str = sec.listing_date.isoformat() if sec.listing_date else "未提供"
            ind_str = sec.primary_industry or "未提供"
            lines.extend([
                f"【標的 {idx}】{sec.name} ({sec.code}) | 市場: {mkt_str} | 產業: {ind_str}",
                f"  - 所屬題材: {theme_str} | 掛牌: {listing_str} | 基準時間: {_fmt_dt(s.as_of)}",
            ])

        lines.extend([
            "",
            "二、價格與區間報酬率橫向對比",
        ])
        for s in snapshots:
            sec = s.security
            p = s.price
            r = s.returns
            if p and p.close is not None:
                vol_lots = _fmt_dec(Decimal(p.volume_shares or 0) / Decimal(1000), " 張")
                lines.append(
                    f"• [{sec.code} {sec.name}] 最新價: {_fmt_dec(p.close, ' 元')} | "
                    f"成交量: {vol_lots} | 1D: {_fmt_pct(r.return_1d)} | "
                    f"5D: {_fmt_pct(r.return_5d)} | 10D: {_fmt_pct(r.return_10d)} | "
                    f"30D: {_fmt_pct(r.return_30d)} | 1Y: {_fmt_pct(r.return_1y)}"
                )
            else:
                lines.append(f"• [{sec.code} {sec.name}] 價格與報酬數據：UNAVAILABLE")

        lines.extend([
            "",
            "三、技術指標綜合對比 (Technical Indicators)",
        ])
        for s in snapshots:
            sec = s.security
            t = s.technicals
            if t and t.data_status != PromptSectionStatus.NO_DATA:
                lines.extend([
                    (
                        f"• [{sec.code} {sec.name}] 均線: MA5={_fmt_dec(t.ma5)} / "
                        f"MA20={_fmt_dec(t.ma20)} / MA60={_fmt_dec(t.ma60)} / "
                        f"MA240={_fmt_dec(t.ma240)}"
                    ),
                    (
                        f"  指標: RSI(14)={_fmt_dec(t.rsi)} | "
                        f"KD(9,3)={_fmt_dec(t.kd_k)}/{_fmt_dec(t.kd_d)} | "
                        f"MACD_Hist={_fmt_dec(t.macd_hist)} | "
                        f"布林中軌={_fmt_dec(t.bollinger_middle)} | ATR={_fmt_dec(t.atr)}"
                    ),
                ])
            else:
                lines.append(f"• [{sec.code} {sec.name}] 技術指標數據：UNAVAILABLE")

        lines.extend([
            "",
            "四、三大法人籌碼動向對比 (Institutional Trading)",
        ])
        for s in snapshots:
            sec = s.security
            inst = s.institutional
            if inst and inst.data_status != PromptSectionStatus.NO_DATA:
                f1 = _fmt_dec(Decimal(inst.latest_day.foreign_net_shares or 0) / 1000)
                t1 = _fmt_dec(Decimal(inst.latest_day.trust_net_shares or 0) / 1000)
                tot1 = _fmt_dec(Decimal(inst.latest_day.total_net_shares or 0) / 1000)
                f5 = _fmt_dec(Decimal(inst.cum_5d.foreign_net_shares or 0) / 1000)
                t5 = _fmt_dec(Decimal(inst.cum_5d.trust_net_shares or 0) / 1000)
                tot5 = _fmt_dec(Decimal(inst.cum_5d.total_net_shares or 0) / 1000)
                lines.extend([
                    (
                        f"• [{sec.code} {sec.name}] 單日買賣超(張): "
                        f"外資 {f1} | 投信 {t1} | 合計 {tot1}"
                    ),
                    (
                        f"  5日累計(張): 外資 {f5} | 投信 {t5} | 合計 {tot5} | "
                        f"連續: 外資 {_fmt_int(inst.consecutive_foreign_days, '日')} / "
                        f"投信 {_fmt_int(inst.consecutive_trust_days, '日')}"
                    ),
                ])
            else:
                lines.append(f"• [{sec.code} {sec.name}] 三大法人數據：UNAVAILABLE")

        lines.extend([
            "",
            "五、信用交易與借券對比 (Margin & Lending)",
        ])
        for s in snapshots:
            sec = s.security
            c = s.credit
            if c and c.data_status != PromptSectionStatus.NO_DATA:
                lines.append(
                    f"• [{sec.code} {sec.name}] 融資餘額: {_fmt_int(c.margin_balance, '張')}"
                    f"({_fmt_int(c.margin_change)}) | 融券: {_fmt_int(c.short_balance, '張')}"
                    f"({_fmt_int(c.short_change)}) | "
                    f"券資比: {_fmt_dec(c.short_margin_ratio, '%')} | "
                    f"借券賣出餘額: {_fmt_int(c.lending_balance, '股')}"
                )
            else:
                lines.append(f"• [{sec.code} {sec.name}] 信用與借券數據：UNAVAILABLE")

        lines.extend([
            "",
            "六、所屬產業強弱度對比",
        ])
        for s in snapshots:
            sec = s.security
            ind = s.industry
            if ind and ind.data_status != PromptSectionStatus.NO_DATA and ind.industry_name:
                rk_str = f"第 {ind.rank or 'NULL'} 名 / 共 {ind.total_industries or 'NULL'} 個產業"
                lines.append(
                    f"• [{sec.code} {sec.name}] 產業: {ind.industry_name} | "
                    f"強弱排名: {rk_str} (強弱分數: {_fmt_dec(ind.strength_score)})"
                )
            else:
                lines.append(f"• [{sec.code} {sec.name}] 產業強弱指標：UNAVAILABLE")

        lines.extend([
            "",
            "七、全市場與衍生品總體環境 (統一基準 Context)",
        ])
        if mkt and mkt.data_status != PromptSectionStatus.NO_DATA:
            inst_spot_yi = (
                _fmt_dec((mkt.institutional_spot_net or Decimal(0)) / Decimal(100000000), " 億元")
                if mkt.institutional_spot_net is not None
                else "NULL"
            )
            lines.extend([
                (
                    f"• 加權指數 (TAIEX)：{_fmt_dec(mkt.taiex_close, ' 點')} "
                    f"(漲跌幅: {_fmt_pct(mkt.taiex_change_pct)}) | 法人現貨買賣超: {inst_spot_yi}"
                ),
                (
                    f"• 市場漲跌家數：上漲 {mkt.advances_count or 'NULL'} 家 | "
                    f"下跌 {mkt.declines_count or 'NULL'} 家"
                ),
            ])
        else:
            lines.append("• 大盤市場數據：UNAVAILABLE")

        if deriv and deriv.data_status != PromptSectionStatus.NO_DATA:
            lines.extend([
                (
                    f"• 台指期收盤: {_fmt_dec(deriv.tx_close, '點')} | "
                    f"外資台指期淨未平倉: {_fmt_int(deriv.foreign_futures_net_oi, '口')} | "
                    f"選擇權 Put/Call Ratio: {_fmt_dec(deriv.option_put_call_ratio, '%')} | "
                    f"VIX: {deriv.vix_status}"
                ),
            ])

        lines.extend([
            "",
            "八、我的投資組合持股現況對比",
        ])
        has_any_pos = any(s.portfolio_position is not None for s in snapshots)
        if has_any_pos:
            for s in snapshots:
                sec = s.security
                pos = s.portfolio_position
                if pos:
                    lines.append(
                        f"• [{sec.code} {sec.name}]【已持有】"
                        f"持有股數: {_fmt_int(pos.shares, '股')} | "
                        f"均價: {_fmt_dec(pos.moving_average_cost, '元')} | "
                        f"市值: {_fmt_dec(pos.latest_market_value, '元')} | "
                        f"未實現損益: {_fmt_dec(pos.unrealized_pnl, '元')} "
                        f"({_fmt_pct(pos.unrealized_pnl_pct)})"
                    )
                else:
                    lines.append(f"• [{sec.code} {sec.name}]【未持有 / 觀察名單】")
        else:
            lines.append("• 目前投資組合中未持有上述任何一檔標的（皆為候選觀察名單）。")

        lines.extend([
            "",
            "九、各標的資料品質狀態對比",
        ])
        for s in snapshots:
            sec = s.security
            dq = s.data_quality
            note_str = f" (註記: {', '.join(dq.freshness_notes)})" if dq.freshness_notes else ""
            lines.append(
                f"• [{sec.code} {sec.name}] 狀態: {dq.overall_status.value} "
                f"(完整度: {_fmt_dec(dq.completeness_pct, '%')}){note_str}"
            )

        lines.extend([
            "",
            "=" * 60,
            "【請外部 AI 針對上述標的進行深入橫向對比分析並回答以下 10 項問題】",
            "",
            (
                "1. 【基本面與成長動能對比】：比較各標的近月營收爆發力、"
                "產業位階與未來 1~2 年獲利成長性。"
            ),
            (
                "2. 【股價趨勢與均線架構強弱】：比較各標的在短中長期均線上的多空排列完整度，"
                "評估誰的趨勢最為強勁。"
            ),
            (
                "3. 【技術指標動能與超買超賣】：綜合評估 RSI、KD、MACD 與布林通道位階，"
                "指出誰動能最強、誰面臨背離。"
            ),
            (
                "4. 【法人籌碼偏好與集中度】：對比外資與投信在近 1D、5D、10D 之資金流向，"
                "分析法人當前最偏好之標的。"
            ),
            (
                "5. 【散戶信用浮額與軋空/多殺多風險】：比較融資券變化、券資比與借券賣出，"
                "分析各標的之籌碼穩定度。"
            ),
            (
                "6. 【產業族群位階與資金輪動】：對比各標的所屬產業強弱度排名，"
                "分析誰位居強勢族群主流地位。"
            ),
            (
                "7. 【估值水準與性價比 (Valuation)】：對比各標的本益比、殖利率或市場評價水準，"
                "評估何者性價比較高。"
            ),
            (
                "8. 【各自之關鍵利多催化劑 (Bullish Catalysts)】：條列每檔股票未來 1~6 個月內"
                "可能推升股價之核心題材。"
            ),
            (
                "9. 【各自之主要下行風險 (Risk Factors)】：條列每檔股票面臨之主要營運、"
                "競爭、評價修正或破位風險。"
            ),
            (
                "10. 【綜合 Risk / Reward 與投資優先級評估】：綜合上述維度，"
                "給出明確之排序與建議。"
            ),
            "",
            "【請於回覆中明確給出以下 5 項排名輸出（由優至劣）】：",
            "  (a) 營運成長動能排名：",
            "  (b) 技術多頭架構排名：",
            "  (c) 法人籌碼偏好排名：",
            "  (d) 估值吸引力排名：",
            "  (e) 綜合 Risk / Reward 投資優先級排名：",
            "",
            "【持股配置與換股策略指引】：",
            (
                "  - 若已持有其中標的：分析續抱條件、獲利調節時機，"
                "或是否有更佳標的值得換股之確認條件；"
            ),
            "  - 若尚未持有任何標的：給予新進資金之佈局優先順序、進場時機與嚴格停損風控防線。",
            "",
            "※ 請依序結構化輸出，給予清晰、量化佐證且條理分明之多股對比分析報告。※",
        ])

        return "\n".join(lines)
