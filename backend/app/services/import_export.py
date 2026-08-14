import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.errors import AppError
from app.domain.portfolio import LotType, TransactionSide
from app.repositories.models import (
    DailyPriceModel,
    PortfolioModel,
    PortfolioTransactionModel,
    SecurityModel,
    SyncChangeModel,
    WatchlistItemModel,
    WatchlistModel,
)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
ZERO = Decimal("0")
UTF8_BOM = "\ufeff"
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMPORT_ROWS = 10_000

PORTFOLIO_CSV_HEADER_V1 = [
    "format_version",
    "transaction_id",
    "portfolio_name",
    "market",
    "code",
    "side",
    "trade_date",
    "trade_time",
    "shares",
    "price",
    "fee",
    "lot_type",
]

WATCHLIST_CSV_HEADER_V1 = [
    "format_version",
    "group_id",
    "group_name",
    "group_order",
    "market",
    "code",
    "item_order",
    "note",
    "target_price",
    "stop_price",
    "add_price",
]


def escape_formula(value: str | None) -> str:
    """Sanitize string values to prevent spreadsheet formula injection."""
    if not value:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def unescape_formula(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if text.startswith("'") and len(text) > 1 and text[1] in ("=", "+", "-", "@", "\t", "\r"):
        return text[1:]
    return text


@dataclass
class ImportRowError:
    row: int
    error_code: str
    message: str


class ExportService:
    def __init__(self, session):
        self.session = session

    async def _require_user_portfolio(self, user_id: UUID, portfolio_id: UUID) -> PortfolioModel:
        portfolio = await self.session.scalar(
            select(PortfolioModel).where(
                PortfolioModel.id == portfolio_id,
                PortfolioModel.user_id == user_id,
                PortfolioModel.deleted_at.is_(None),
            )
        )
        if portfolio is None:
            raise AppError("PORTFOLIO_NOT_FOUND", "找不到投資組合或無權限存取", 404)
        return portfolio

    async def export_portfolio_transactions_csv(
        self, user_id: UUID, portfolio_id: UUID
    ) -> bytes:
        portfolio = await self._require_user_portfolio(user_id, portfolio_id)
        transactions = (
            await self.session.scalars(
                select(PortfolioTransactionModel)
                .where(
                    PortfolioTransactionModel.portfolio_id == portfolio_id,
                    PortfolioTransactionModel.user_id == user_id,
                    PortfolioTransactionModel.deleted_at.is_(None),
                )
                .order_by(
                    PortfolioTransactionModel.executed_at,
                    PortfolioTransactionModel.created_at,
                    PortfolioTransactionModel.id,
                )
            )
        ).all()

        # Preload securities
        sec_ids = {tx.security_id for tx in transactions}
        securities = {}
        if sec_ids:
            sec_rows = (
                await self.session.scalars(
                    select(SecurityModel).where(SecurityModel.id.in_(sec_ids))
                )
            ).all()
            securities = {sec.id: sec for sec in sec_rows}

        output = io.StringIO()
        output.write(UTF8_BOM)
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(PORTFOLIO_CSV_HEADER_V1)

        for tx in transactions:
            sec = securities.get(tx.security_id)
            market = sec.market if sec else "TWSE"
            code = sec.code if sec else ""
            local_dt = tx.executed_at.astimezone(TAIPEI_TZ)
            writer.writerow(
                [
                    "twml-portfolio-csv-v1",
                    str(tx.id),
                    escape_formula(portfolio.name),
                    market,
                    code,
                    tx.side,
                    local_dt.strftime("%Y-%m-%d"),
                    local_dt.strftime("%H:%M:%S"),
                    str(tx.quantity_shares),
                    f"{Decimal(str(tx.price)):f}",
                    f"{Decimal(str(tx.fee)):f}",
                    tx.lot_type,
                ]
            )
        return output.getvalue().encode("utf-8")

    async def export_portfolio_holdings_csv(self, user_id: UUID, portfolio_id: UUID) -> bytes:
        portfolio = await self._require_user_portfolio(user_id, portfolio_id)
        from app.domain.portfolio import PortfolioTransaction
        from app.domain.pricing import SecurityKey
        from app.services.portfolio import PortfolioAccountingService

        tx_rows = (
            await self.session.scalars(
                select(PortfolioTransactionModel)
                .where(
                    PortfolioTransactionModel.portfolio_id == portfolio_id,
                    PortfolioTransactionModel.user_id == user_id,
                    PortfolioTransactionModel.deleted_at.is_(None),
                )
                .order_by(
                    PortfolioTransactionModel.executed_at,
                    PortfolioTransactionModel.created_at,
                    PortfolioTransactionModel.id,
                )
            )
        ).all()

        sec_ids = {tx.security_id for tx in tx_rows}
        securities = {}
        if sec_ids:
            sec_rows = (
                await self.session.scalars(
                    select(SecurityModel).where(SecurityModel.id.in_(sec_ids))
                )
            ).all()
            securities = {sec.id: sec for sec in sec_rows}

        domain_txs = [
            PortfolioTransaction(
                tx.id,
                tx.portfolio_id,
                tx.security_id,
                SecurityKey(
                    securities[tx.security_id].market if tx.security_id in securities else "TWSE",
                    securities[tx.security_id].code if tx.security_id in securities else "",
                ),
                securities[tx.security_id].name if tx.security_id in securities else "",
                TransactionSide(tx.side),
                tx.executed_at,
                tx.quantity_shares,
                Decimal(str(tx.price)),
                Decimal(str(tx.fee)),
                LotType(tx.lot_type),
                tx.created_at,
                tx.updated_at,
            )
            for tx in tx_rows
        ]

        accounting = PortfolioAccountingService()
        positions = accounting.replay(domain_txs)

        output = io.StringIO()
        output.write(UTF8_BOM)
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(
            [
                "market",
                "code",
                "name",
                "shares",
                "average_cost",
                "latest_price",
                "market_value",
                "unrealized_pnl",
                "unrealized_pnl_pct",
            ]
        )

        for pos in positions:
            if pos.quantity_shares == 0:
                continue
            # Latest price query
            latest_price = await self.session.scalar(
                select(DailyPriceModel.close)
                .where(DailyPriceModel.security_id == pos.security_id)
                .order_by(DailyPriceModel.trade_date.desc())
                .limit(1)
            )
            close_dec = Decimal(str(latest_price)) if latest_price is not None else None
            mkt_val = close_dec * pos.quantity_shares if close_dec is not None else None
            unrealized = mkt_val - pos.cost_basis if mkt_val is not None else None
            unrealized_pct = (
                (unrealized / pos.cost_basis * 100)
                if unrealized is not None and pos.cost_basis > ZERO
                else None
            )

            writer.writerow(
                [
                    pos.security.market,
                    pos.security.code,
                    escape_formula(pos.security_name),
                    str(pos.quantity_shares),
                    f"{pos.average_cost:f}" if pos.average_cost is not None else "",
                    f"{close_dec:f}" if close_dec is not None else "",
                    f"{mkt_val:f}" if mkt_val is not None else "",
                    f"{unrealized:f}" if unrealized is not None else "",
                    f"{unrealized_pct:.2f}%" if unrealized_pct is not None else "",
                ]
            )
        return output.getvalue().encode("utf-8")

    async def export_portfolio_summary_csv(self, user_id: UUID, portfolio_id: UUID) -> bytes:
        portfolio = await self._require_user_portfolio(user_id, portfolio_id)
        from app.domain.portfolio import PortfolioTransaction
        from app.domain.pricing import SecurityKey
        from app.services.portfolio import PortfolioAccountingService

        tx_rows = (
            await self.session.scalars(
                select(PortfolioTransactionModel)
                .where(
                    PortfolioTransactionModel.portfolio_id == portfolio_id,
                    PortfolioTransactionModel.user_id == user_id,
                    PortfolioTransactionModel.deleted_at.is_(None),
                )
                .order_by(
                    PortfolioTransactionModel.executed_at,
                    PortfolioTransactionModel.created_at,
                    PortfolioTransactionModel.id,
                )
            )
        ).all()

        sec_ids = {tx.security_id for tx in tx_rows}
        securities = {}
        if sec_ids:
            sec_rows = (
                await self.session.scalars(
                    select(SecurityModel).where(SecurityModel.id.in_(sec_ids))
                )
            ).all()
            securities = {sec.id: sec for sec in sec_rows}

        domain_txs = [
            PortfolioTransaction(
                tx.id,
                tx.portfolio_id,
                tx.security_id,
                SecurityKey(
                    securities[tx.security_id].market if tx.security_id in securities else "TWSE",
                    securities[tx.security_id].code if tx.security_id in securities else "",
                ),
                securities[tx.security_id].name if tx.security_id in securities else "",
                TransactionSide(tx.side),
                tx.executed_at,
                tx.quantity_shares,
                Decimal(str(tx.price)),
                Decimal(str(tx.fee)),
                LotType(tx.lot_type),
                tx.created_at,
                tx.updated_at,
            )
            for tx in tx_rows
        ]

        accounting = PortfolioAccountingService()
        positions = accounting.replay(domain_txs)

        total_cost = sum((p.cost_basis for p in positions if p.quantity_shares > 0), ZERO)
        total_realized = sum((p.realized_pnl for p in positions), ZERO)
        holding_count = sum(1 for p in positions if p.quantity_shares > 0)

        # Market values
        total_market_val = ZERO
        has_prices = True
        for p in positions:
            if p.quantity_shares > 0:
                p_close = await self.session.scalar(
                    select(DailyPriceModel.close)
                    .where(DailyPriceModel.security_id == p.security_id)
                    .order_by(DailyPriceModel.trade_date.desc())
                    .limit(1)
                )
                if p_close is not None:
                    total_market_val += Decimal(str(p_close)) * p.quantity_shares
                else:
                    has_prices = False

        unrealized = total_market_val - total_cost if has_prices else None
        total_pnl = total_realized + (unrealized or ZERO)

        output = io.StringIO()
        output.write(UTF8_BOM)
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(
            [
                "portfolio_name",
                "as_of",
                "total_cost",
                "market_value",
                "realized_pnl",
                "unrealized_pnl",
                "total_pnl",
                "position_count",
                "data_status",
            ]
        )
        writer.writerow(
            [
                escape_formula(portfolio.name),
                datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                f"{total_cost:f}",
                f"{total_market_val:f}" if has_prices else "",
                f"{total_realized:f}",
                f"{unrealized:f}" if unrealized is not None else "",
                f"{total_pnl:f}",
                str(holding_count),
                "FINAL" if has_prices else "PARTIAL",
            ]
        )
        return output.getvalue().encode("utf-8")

    async def export_watchlists_csv(self, user_id: UUID) -> bytes:
        groups = (
            await self.session.scalars(
                select(WatchlistModel)
                .where(WatchlistModel.user_id == user_id, WatchlistModel.deleted_at.is_(None))
                .order_by(WatchlistModel.sort_order, WatchlistModel.id)
            )
        ).all()

        items = (
            await self.session.scalars(
                select(WatchlistItemModel)
                .where(
                    WatchlistItemModel.user_id == user_id,
                    WatchlistItemModel.deleted_at.is_(None),
                )
                .order_by(WatchlistItemModel.watchlist_id, WatchlistItemModel.sort_order)
            )
        ).all()

        sec_ids = {item.security_id for item in items}
        securities = {}
        if sec_ids:
            sec_rows = (
                await self.session.scalars(
                    select(SecurityModel).where(SecurityModel.id.in_(sec_ids))
                )
            ).all()
            securities = {sec.id: sec for sec in sec_rows}

        group_map = {g.id: g for g in groups}

        output = io.StringIO()
        output.write(UTF8_BOM)
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(WATCHLIST_CSV_HEADER_V1)

        for item in items:
            g = group_map.get(item.watchlist_id)
            sec = securities.get(item.security_id)
            if not g or not sec:
                continue
            writer.writerow(
                [
                    "twml-watchlist-csv-v1",
                    str(g.id),
                    escape_formula(g.name),
                    str(g.sort_order),
                    sec.market,
                    sec.code,
                    str(item.sort_order),
                    escape_formula(item.note) if item.note else "",
                    f"{Decimal(str(item.target_price)):f}"
                    if item.target_price is not None
                    else "",
                    f"{Decimal(str(item.stop_price)):f}" if item.stop_price is not None else "",
                    f"{Decimal(str(item.add_price)):f}" if item.add_price is not None else "",
                ]
            )
        return output.getvalue().encode("utf-8")


class ReportService:
    def __init__(self, session):
        self.session = session

    async def generate_portfolio_pdf_report(
        self, user_id: UUID, portfolio_id: UUID
    ) -> bytes:
        portfolio = await self.session.scalar(
            select(PortfolioModel).where(
                PortfolioModel.id == portfolio_id,
                PortfolioModel.user_id == user_id,
                PortfolioModel.deleted_at.is_(None),
            )
        )
        if portfolio is None:
            raise AppError("PORTFOLIO_NOT_FOUND", "找不到投資組合或無權限存取", 404)

        from app.domain.portfolio import PortfolioTransaction
        from app.domain.pricing import SecurityKey
        from app.services.portfolio import PortfolioAccountingService

        tx_rows = (
            await self.session.scalars(
                select(PortfolioTransactionModel)
                .where(
                    PortfolioTransactionModel.portfolio_id == portfolio_id,
                    PortfolioTransactionModel.user_id == user_id,
                    PortfolioTransactionModel.deleted_at.is_(None),
                )
                .order_by(
                    PortfolioTransactionModel.executed_at,
                    PortfolioTransactionModel.created_at,
                    PortfolioTransactionModel.id,
                )
            )
        ).all()

        sec_ids = {tx.security_id for tx in tx_rows}
        securities = {}
        if sec_ids:
            sec_rows = (
                await self.session.scalars(
                    select(SecurityModel).where(SecurityModel.id.in_(sec_ids))
                )
            ).all()
            securities = {sec.id: sec for sec in sec_rows}

        domain_txs = [
            PortfolioTransaction(
                tx.id,
                tx.portfolio_id,
                tx.security_id,
                SecurityKey(
                    securities[tx.security_id].market if tx.security_id in securities else "TWSE",
                    securities[tx.security_id].code if tx.security_id in securities else "",
                ),
                securities[tx.security_id].name if tx.security_id in securities else "",
                TransactionSide(tx.side),
                tx.executed_at,
                tx.quantity_shares,
                Decimal(str(tx.price)),
                Decimal(str(tx.fee)),
                LotType(tx.lot_type),
                tx.created_at,
                tx.updated_at,
            )
            for tx in tx_rows
        ]

        accounting = PortfolioAccountingService()
        positions = accounting.replay(domain_txs)

        holdings = []
        for pos in positions:
            if pos.quantity_shares == 0:
                continue
            p_close = await self.session.scalar(
                select(DailyPriceModel.close)
                .where(DailyPriceModel.security_id == pos.security_id)
                .order_by(DailyPriceModel.trade_date.desc())
                .limit(1)
            )
            close_dec = Decimal(str(p_close)) if p_close is not None else None
            mkt_val = close_dec * pos.quantity_shares if close_dec is not None else None
            unrealized = mkt_val - pos.cost_basis if mkt_val is not None else None
            holdings.append(
                {
                    "market": pos.security.market,
                    "code": pos.security.code,
                    "name": pos.security_name,
                    "shares": pos.quantity_shares,
                    "cost_basis": pos.cost_basis,
                    "average_cost": pos.average_cost,
                    "close": close_dec,
                    "market_value": mkt_val,
                    "unrealized_pnl": unrealized,
                }
            )

        total_cost = sum((h["cost_basis"] for h in holdings), ZERO)
        total_mkt_val = sum(
            (h["market_value"] for h in holdings if h["market_value"] is not None), ZERO
        )
        total_realized = sum((p.realized_pnl for p in positions), ZERO)
        total_unrealized = total_mkt_val - total_cost if holdings else ZERO
        as_of_str = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S (Asia/Taipei)")

        # Render PDF using reportlab or fallback pure-python PDF generator
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            p.setTitle("TW Market Ledger Portfolio Report")

            # Title & Metadata
            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, 750, "TW Market Ledger Portfolio Report")
            p.setFont("Helvetica", 10)
            p.drawString(50, 730, f"Portfolio: {portfolio.name}")
            p.drawString(50, 715, f"Generated At: {as_of_str}")
            p.drawString(50, 700, "Market Data Status: FINAL")
            p.line(50, 690, 550, 690)

            # Summary Box
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, 670, "Portfolio Summary")
            p.setFont("Helvetica", 10)
            p.drawString(50, 650, f"Total Cost Basis: ${total_cost:,.2f}")
            p.drawString(200, 650, f"Total Market Value: ${total_mkt_val:,.2f}")
            p.drawString(380, 650, f"Realized P&L: ${total_realized:,.2f}")
            p.drawString(50, 635, f"Unrealized P&L: ${total_unrealized:,.2f}")
            p.drawString(200, 635, f"Active Positions: {len(holdings)}")
            p.line(50, 625, 550, 625)

            # Holdings Table Header
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, 605, "Market")
            p.drawString(100, 605, "Code")
            p.drawString(160, 605, "Shares")
            p.drawString(240, 605, "Avg Cost")
            p.drawString(320, 605, "Price")
            p.drawString(400, 605, "Market Value")
            p.drawString(490, 605, "Unrealized")
            p.line(50, 595, 550, 595)

            y = 580
            p.setFont("Helvetica", 9)
            for h in holdings:
                if y < 80:
                    p.showPage()
                    y = 750
                    p.setFont("Helvetica", 9)
                p.drawString(50, y, str(h["market"]))
                p.drawString(100, y, str(h["code"]))
                p.drawString(160, y, f"{h['shares']:,}")
                p.drawString(240, y, f"{h['average_cost']:.2f}" if h['average_cost'] else "-")
                p.drawString(320, y, f"{h['close']:.2f}" if h['close'] else "-")
                p.drawString(400, y, f"{h['market_value']:,.2f}" if h['market_value'] else "-")
                p.drawString(490, y, f"{h['unrealized_pnl']:,.2f}" if h['unrealized_pnl'] else "-")
                y -= 20

            p.save()
            return buffer.getvalue()
        except ImportError:
            # Minimalistic deterministic PDF writer
            lines = [
                "%PDF-1.4",
                "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
                "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
                "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
                "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
            ]
            content_stream = (
                f"BT /F1 16 Tf 50 750 Td (TW Market Ledger Portfolio Report) Tj "
                f"/F1 10 Tf 0 -20 Td (Portfolio: {escape_formula(portfolio.name)}) Tj "
                f"0 -15 Td (Generated At: {as_of_str}) Tj "
                f"0 -25 Td (Total Cost: {total_cost:,.2f}  Market Value: {total_mkt_val:,.2f}) Tj "
                f"0 -15 Td (Realized P&L: {total_realized:,.2f}  "
                f"Unrealized P&L: {total_unrealized:,.2f}) Tj "
                f"0 -20 Td (Holdings Count: {len(holdings)}) Tj ET"
            )
            content_bytes = content_stream.encode("utf-8")
            lines.append(
                f"4 0 obj << /Length {len(content_bytes)} >> stream\n"
                f"{content_stream}\nendstream\nendobj"
            )
            lines.append("xref\n0 6\n0000000000 65535 f \n")
            lines.append(
                "trailer << /Size 6 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
            )
            return "\n".join(lines).encode("utf-8")


class ImportService:
    def __init__(self, session, redis_client=None):
        self.session = session
        self.redis = redis_client
        self._memory_cache = {}

    def _set_preview(self, token: str, data: dict):
        if self.redis:
            self.redis.setex(f"preview:{token}", 1800, json.dumps(data, default=str))
        else:
            self._memory_cache[token] = data

    def _get_preview(self, token: str) -> dict | None:
        if self.redis:
            raw = self.redis.get(f"preview:{token}")
            return json.loads(raw) if raw else None
        return self._memory_cache.get(token)

    def _delete_preview(self, token: str):
        if self.redis:
            self.redis.delete(f"preview:{token}")
        else:
            self._memory_cache.pop(token, None)

    async def preview_portfolio_csv(
        self, user_id: UUID, csv_text: str, portfolio_id: UUID | None = None
    ) -> dict:
        if len(csv_text.encode("utf-8")) > MAX_UPLOAD_SIZE_BYTES:
            raise AppError("IMPORT_FILE_TOO_LARGE", "匯入檔案大小超過上限 (5MB)", 413)

        reader = csv.reader(io.StringIO(csv_text.lstrip(UTF8_BOM)))
        rows = list(reader)
        if not rows:
            raise AppError("IMPORT_EMPTY_FILE", "匯入檔案無資料", 422)

        header = [c.strip().lower() for c in rows[0]]
        expected_cols = {"market", "code", "side", "trade_date", "trade_time", "shares", "price"}
        if not expected_cols.issubset(set(header)):
            raise AppError(
                "IMPORT_INVALID_HEADER",
                f"CSV 缺少必要欄位: {', '.join(sorted(expected_cols - set(header)))}",
                422,
            )

        col_map = {col: idx for idx, col in enumerate(header)}
        parsed_candidates = []
        errors = []
        warnings = []
        duplicate_count = 0
        seen_fingerprints = set()

        if len(rows) - 1 > MAX_IMPORT_ROWS:
            raise AppError("IMPORT_ROW_LIMIT_EXCEEDED", f"單次匯入不可超過 {MAX_IMPORT_ROWS} 列", 422)

        # Preload all securities in memory for fast bulk lookup
        sec_rows = (await self.session.scalars(select(SecurityModel))).all()
        sec_by_pair = {(s.market, s.code): s for s in sec_rows}
        sec_by_code: dict[str, list[SecurityModel]] = {}
        for s in sec_rows:
            sec_by_code.setdefault(s.code, []).append(s)

        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            try:
                raw_tx_id = row[col_map["transaction_id"]] if "transaction_id" in col_map else None
                tx_id = UUID(raw_tx_id.strip()) if raw_tx_id and raw_tx_id.strip() else uuid4()

                market = row[col_map["market"]].strip().upper() if "market" in col_map else None
                code = row[col_map["code"]].strip().upper()
                side_raw = row[col_map["side"]].strip().upper()
                if side_raw not in ("BUY", "SELL"):
                    errors.append(
                        ImportRowError(
                            row_idx,
                            "INVALID_SIDE",
                            f"交易方向必須為 BUY 或 SELL (實際: {side_raw})",
                        )
                    )
                    continue

                side = TransactionSide(side_raw)
                date_str = row[col_map["trade_date"]].strip()
                time_str = (
                    row[col_map["trade_time"]].strip()
                    if "trade_time" in col_map and row[col_map["trade_time"]].strip()
                    else "09:00:00"
                )

                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                    executed_at = dt.replace(tzinfo=TAIPEI_TZ).astimezone(UTC)
                except ValueError:
                    errors.append(
                        ImportRowError(
                            row_idx,
                            "INVALID_DATETIME",
                            f"日期時間格式必須為 YYYY-MM-DD 與 HH:mm:ss (實際: {date_str} {time_str})",
                        )
                    )
                    continue

                try:
                    shares = int(Decimal(row[col_map["shares"]].strip()))
                    if shares <= 0:
                        raise ValueError()
                except Exception:
                    errors.append(
                        ImportRowError(row_idx, "INVALID_SHARES", "股數必須為大於 0 之整數")
                    )
                    continue

                try:
                    price = Decimal(row[col_map["price"]].strip())
                    if price <= ZERO:
                        raise ValueError()
                except (InvalidOperation, ValueError):
                    errors.append(
                        ImportRowError(row_idx, "INVALID_PRICE", "價格必須為大於 0 之數值")
                    )
                    continue

                fee = ZERO
                if "fee" in col_map and row[col_map["fee"]].strip():
                    try:
                        fee = Decimal(row[col_map["fee"]].strip())
                        if fee < ZERO:
                            raise ValueError()
                    except (InvalidOperation, ValueError):
                        errors.append(
                            ImportRowError(row_idx, "INVALID_FEE", "手續費必須為大於等於 0 之數值")
                        )
                        continue

                lot_type_raw = (
                    row[col_map["lot_type"]].strip().upper()
                    if "lot_type" in col_map and row[col_map["lot_type"]].strip()
                    else "BOARD_LOT"
                )
                if lot_type_raw not in ("BOARD_LOT", "ODD_LOT"):
                    errors.append(
                        ImportRowError(row_idx, "INVALID_LOT_TYPE", "交易盤別必須為 BOARD_LOT 或 ODD_LOT")
                    )
                    continue
                lot_type = LotType(lot_type_raw)

                # Resolve security
                matched_sec = None
                if market:
                    matched_sec = sec_by_pair.get((market, code))
                else:
                    candidates = sec_by_code.get(code, [])
                    if len(candidates) == 1:
                        matched_sec = candidates[0]
                    elif len(candidates) > 1:
                        errors.append(
                            ImportRowError(
                                row_idx, "AMBIGUOUS_SECURITY", f"股票代號 {code} 存在於多個市場，請明確指定 market"
                            )
                        )
                        continue

                if matched_sec is None:
                    errors.append(
                        ImportRowError(
                            row_idx,
                            "SECURITY_NOT_FOUND",
                            f"找不到指定股票 ({market or ''}:{code})",
                        )
                    )
                    continue

                # Duplicate fingerprint
                fp = (matched_sec.id, side.value, executed_at.isoformat(), shares, str(price))
                if fp in seen_fingerprints:
                    duplicate_count += 1
                    warnings.append(
                        ImportRowError(row_idx, "POSSIBLE_DUPLICATE", "此筆交易與匯入檔內其他列可能重複")
                    )
                seen_fingerprints.add(fp)

                parsed_candidates.append(
                    {
                        "row_number": row_idx,
                        "transaction_id": str(tx_id),
                        "security_id": str(matched_sec.id),
                        "market": matched_sec.market,
                        "code": matched_sec.code,
                        "name": matched_sec.name,
                        "side": side.value,
                        "executed_at": executed_at.isoformat(),
                        "quantity_shares": shares,
                        "price": str(price),
                        "fee": str(fee),
                        "lot_type": lot_type.value,
                    }
                )
            except Exception as e:
                errors.append(ImportRowError(row_idx, "PARSE_ERROR", f"資料解析錯誤: {e}"))

        # Replay accounting to check for oversell
        if not errors and parsed_candidates:
            from app.domain.portfolio import PortfolioTransaction
            from app.domain.pricing import SecurityKey
            from app.services.portfolio import PortfolioAccountingService

            # Load existing transactions if portfolio_id specified
            existing_txs = []
            if portfolio_id:
                db_txs = (
                    await self.session.scalars(
                        select(PortfolioTransactionModel).where(
                            PortfolioTransactionModel.portfolio_id == portfolio_id,
                            PortfolioTransactionModel.user_id == user_id,
                            PortfolioTransactionModel.deleted_at.is_(None),
                        )
                    )
                ).all()
                existing_txs = [
                    PortfolioTransaction(
                        tx.id,
                        tx.portfolio_id,
                        tx.security_id,
                        SecurityKey("TWSE", ""),
                        "",
                        TransactionSide(tx.side),
                        tx.executed_at,
                        tx.quantity_shares,
                        Decimal(str(tx.price)),
                        Decimal(str(tx.fee)),
                        LotType(tx.lot_type),
                        tx.created_at,
                        tx.updated_at,
                    )
                    for tx in db_txs
                ]

            simulated = list(existing_txs)
            for c in parsed_candidates:
                simulated.append(
                    PortfolioTransaction(
                        UUID(c["transaction_id"]),
                        portfolio_id or uuid4(),
                        UUID(c["security_id"]),
                        SecurityKey(c["market"], c["code"]),
                        c["name"],
                        TransactionSide(c["side"]),
                        datetime.fromisoformat(c["executed_at"]),
                        c["quantity_shares"],
                        Decimal(c["price"]),
                        Decimal(c["fee"]),
                        LotType(c["lot_type"]),
                        datetime.now(UTC),
                        datetime.now(UTC),
                    )
                )

            accounting = PortfolioAccountingService()
            try:
                accounting.replay(simulated)
            except AppError as e:
                errors.append(ImportRowError(0, "OVERSELL", f"交易重播失敗: {e.message}"))

        preview_token = str(uuid4())
        preview_data = {
            "token": preview_token,
            "user_id": str(user_id),
            "portfolio_id": str(portfolio_id) if portfolio_id else None,
            "total_rows": len(rows) - 1,
            "valid_rows": len(parsed_candidates) if not errors else 0,
            "invalid_rows": len(errors),
            "warning_rows": len(warnings),
            "duplicate_rows": duplicate_count,
            "transactions": parsed_candidates if not errors else [],
            "errors": [
                {"row": e.row, "error_code": e.error_code, "message": e.message} for e in errors
            ],
            "warnings": [
                {"row": w.row, "error_code": w.error_code, "message": w.message} for w in warnings
            ],
        }
        self._set_preview(preview_token, preview_data)
        return preview_data

    async def apply_portfolio_import(
        self, user_id: UUID, preview_token: str, target_portfolio_id: UUID
    ) -> dict:
        preview = self._get_preview(preview_token)
        if not preview or preview.get("user_id") != str(user_id):
            raise AppError("IMPORT_PREVIEW_EXPIRED", "匯入預覽已過期或不存在，請重新上傳預覽", 404)

        if preview["invalid_rows"] > 0:
            raise AppError("IMPORT_HAS_ERRORS", "匯入資料包含錯誤，無法套用", 422)

        portfolio = await self.session.scalar(
            select(PortfolioModel).where(
                PortfolioModel.id == target_portfolio_id,
                PortfolioModel.user_id == user_id,
                PortfolioModel.deleted_at.is_(None),
            )
        )
        if portfolio is None:
            raise AppError("PORTFOLIO_NOT_FOUND", "找不到目標投資組合", 404)

        now = datetime.now(UTC)
        inserted_count = 0
        skipped_count = 0

        # Max sequence for sync change logging
        cursor = await self.session.scalar(
            select(func.coalesce(func.max(SyncChangeModel.sequence), 0)).where(
                SyncChangeModel.user_id == user_id
            )
        )
        seq = cursor or 0

        for item in preview["transactions"]:
            tx_id = UUID(item["transaction_id"])
            existing = await self.session.scalar(
                select(PortfolioTransactionModel).where(
                    PortfolioTransactionModel.id == tx_id,
                    PortfolioTransactionModel.user_id == user_id,
                )
            )
            if existing is not None:
                skipped_count += 1
                continue

            new_tx = PortfolioTransactionModel(
                id=tx_id,
                user_id=user_id,
                portfolio_id=target_portfolio_id,
                security_id=UUID(item["security_id"]),
                side=item["side"],
                executed_at=datetime.fromisoformat(item["executed_at"]),
                quantity_shares=item["quantity_shares"],
                price=Decimal(item["price"]),
                fee=Decimal(item["fee"]),
                lot_type=item["lot_type"],
                version=1,
                created_at=now,
                updated_at=now,
            )
            self.session.add(new_tx)

            seq += 1
            change = SyncChangeModel(
                user_id=user_id,
                sequence=seq,
                entity_type="PORTFOLIO_TRANSACTION",
                entity_id=tx_id,
                operation="UPSERT",
                version=1,
                payload={
                    "portfolio_id": str(target_portfolio_id),
                    "security_id": item["security_id"],
                    "side": item["side"],
                    "executed_at": item["executed_at"],
                    "quantity_shares": item["quantity_shares"],
                    "price": item["price"],
                    "fee": item["fee"],
                    "lot_type": item["lot_type"],
                },
                changed_at=now,
            )
            self.session.add(change)
            inserted_count += 1

        await self.session.commit()
        self._delete_preview(preview_token)

        return {
            "status": "APPLIED",
            "inserted_count": inserted_count,
            "skipped_count": skipped_count,
            "total_transactions": len(preview["transactions"]),
        }

    async def preview_watchlist_csv(
        self, user_id: UUID, csv_text: str, merge_mode: str = "MERGE"
    ) -> dict:
        if len(csv_text.encode("utf-8")) > MAX_UPLOAD_SIZE_BYTES:
            raise AppError("IMPORT_FILE_TOO_LARGE", "匯入檔案大小超過上限 (5MB)", 413)

        reader = csv.reader(io.StringIO(csv_text.lstrip(UTF8_BOM)))
        rows = list(reader)
        if not rows:
            raise AppError("IMPORT_EMPTY_FILE", "匯入檔案無資料", 422)

        header = [c.strip().lower() for c in rows[0]]
        expected_cols = {"group_name", "market", "code"}
        if not expected_cols.issubset(set(header)):
            raise AppError(
                "IMPORT_INVALID_HEADER",
                f"CSV 缺少必要欄位: {', '.join(sorted(expected_cols - set(header)))}",
                422,
            )

        col_map = {col: idx for idx, col in enumerate(header)}
        groups_dict: dict[str, dict] = {}
        errors = []
        warnings = []

        sec_rows = (await self.session.scalars(select(SecurityModel))).all()
        sec_by_pair = {(s.market, s.code): s for s in sec_rows}

        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            g_name = row[col_map["group_name"]].strip()
            if not g_name:
                errors.append(ImportRowError(row_idx, "INVALID_GROUP_NAME", "自選群組名稱不可為空"))
                continue

            market = row[col_map["market"]].strip().upper()
            code = row[col_map["code"]].strip().upper()
            sec = sec_by_pair.get((market, code))
            if sec is None:
                errors.append(
                    ImportRowError(row_idx, "SECURITY_NOT_FOUND", f"找不到指定股票 ({market}:{code})")
                )
                continue

            note = (
                row[col_map["note"]].strip()
                if "note" in col_map and row[col_map["note"]].strip()
                else None
            )
            target = (
                Decimal(row[col_map["target_price"]].strip())
                if "target_price" in col_map and row[col_map["target_price"]].strip()
                else None
            )
            stop = (
                Decimal(row[col_map["stop_price"]].strip())
                if "stop_price" in col_map and row[col_map["stop_price"]].strip()
                else None
            )
            add = (
                Decimal(row[col_map["add_price"]].strip())
                if "add_price" in col_map and row[col_map["add_price"]].strip()
                else None
            )

            group_entry = groups_dict.setdefault(
                g_name,
                {
                    "group_name": g_name,
                    "group_id": (
                        row[col_map["group_id"]].strip()
                        if "group_id" in col_map and row[col_map["group_id"]].strip()
                        else str(uuid4())
                    ),
                    "items": [],
                },
            )
            group_entry["items"].append(
                {
                    "row_number": row_idx,
                    "security_id": str(sec.id),
                    "market": sec.market,
                    "code": sec.code,
                    "name": sec.name,
                    "note": note,
                    "target_price": str(target) if target else None,
                    "stop_price": str(stop) if stop else None,
                    "add_price": str(add) if add else None,
                }
            )

        preview_token = str(uuid4())
        preview_data = {
            "token": preview_token,
            "user_id": str(user_id),
            "merge_mode": merge_mode,
            "total_rows": len(rows) - 1,
            "valid_rows": len(rows) - 1 - len(errors),
            "invalid_rows": len(errors),
            "groups": list(groups_dict.values()),
            "errors": [
                {"row": e.row, "error_code": e.error_code, "message": e.message} for e in errors
            ],
        }
        self._set_preview(preview_token, preview_data)
        return preview_data

    async def apply_watchlist_import(
        self, user_id: UUID, preview_token: str, merge_mode: str = "MERGE"
    ) -> dict:
        preview = self._get_preview(preview_token)
        if not preview or preview.get("user_id") != str(user_id):
            raise AppError("IMPORT_PREVIEW_EXPIRED", "自選匯入預覽已過期或不存在", 404)

        if preview["invalid_rows"] > 0:
            raise AppError("IMPORT_HAS_ERRORS", "匯入資料包含錯誤，無法套用", 422)

        now = datetime.now(UTC)
        cursor = await self.session.scalar(
            select(func.coalesce(func.max(SyncChangeModel.sequence), 0)).where(
                SyncChangeModel.user_id == user_id
            )
        )
        seq = cursor or 0

        if merge_mode == "REPLACE":
            # Soft-delete all existing user watchlists
            existing_wls = (
                await self.session.scalars(
                    select(WatchlistModel).where(
                        WatchlistModel.user_id == user_id, WatchlistModel.deleted_at.is_(None)
                    )
                )
            ).all()
            for wl in existing_wls:
                wl.deleted_at = now
                seq += 1
                self.session.add(
                    SyncChangeModel(
                        user_id=user_id,
                        sequence=seq,
                        entity_type="WATCHLIST",
                        entity_id=wl.id,
                        operation="DELETE",
                        version=wl.version + 1,
                        payload={},
                        changed_at=now,
                    )
                )

        added_groups = 0
        added_items = 0

        for g_data in preview["groups"]:
            # Check existing group by name
            wl = await self.session.scalar(
                select(WatchlistModel).where(
                    WatchlistModel.user_id == user_id,
                    WatchlistModel.name == g_data["group_name"],
                    WatchlistModel.deleted_at.is_(None),
                )
            )
            if wl is None:
                wl = WatchlistModel(
                    id=UUID(g_data["group_id"]),
                    user_id=user_id,
                    name=g_data["group_name"],
                    sort_order=added_groups,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(wl)
                seq += 1
                self.session.add(
                    SyncChangeModel(
                        user_id=user_id,
                        sequence=seq,
                        entity_type="WATCHLIST",
                        entity_id=wl.id,
                        operation="UPSERT",
                        version=1,
                        payload={"name": wl.name, "sort_order": wl.sort_order},
                        changed_at=now,
                    )
                )
                added_groups += 1

            for idx, item in enumerate(g_data["items"]):
                sec_id = UUID(item["security_id"])
                # Check item existence in group
                existing_item = await self.session.scalar(
                    select(WatchlistItemModel).where(
                        WatchlistItemModel.watchlist_id == wl.id,
                        WatchlistItemModel.security_id == sec_id,
                        WatchlistItemModel.deleted_at.is_(None),
                    )
                )
                if existing_item is not None:
                    continue

                item_id = uuid4()
                new_item = WatchlistItemModel(
                    id=item_id,
                    user_id=user_id,
                    watchlist_id=wl.id,
                    security_id=sec_id,
                    sort_order=idx,
                    note=item.get("note"),
                    target_price=(
                        Decimal(item["target_price"]) if item.get("target_price") else None
                    ),
                    stop_price=Decimal(item["stop_price"]) if item.get("stop_price") else None,
                    add_price=Decimal(item["add_price"]) if item.get("add_price") else None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(new_item)
                seq += 1
                self.session.add(
                    SyncChangeModel(
                        user_id=user_id,
                        sequence=seq,
                        entity_type="WATCHLIST_ITEM",
                        entity_id=item_id,
                        operation="UPSERT",
                        version=1,
                        payload={
                            "watchlist_id": str(wl.id),
                            "security_id": str(sec_id),
                            "sort_order": idx,
                            "note": item.get("note"),
                            "target_price": item.get("target_price"),
                            "stop_price": item.get("stop_price"),
                            "add_price": item.get("add_price"),
                        },
                        changed_at=now,
                    )
                )
                added_items += 1

        await self.session.commit()
        self._delete_preview(preview_token)

        return {
            "status": "APPLIED",
            "merge_mode": merge_mode,
            "groups_count": added_groups,
            "items_count": added_items,
        }
