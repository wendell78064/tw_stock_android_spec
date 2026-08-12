from decimal import ROUND_HALF_UP, Decimal

from app.domain.industry_strength import (
    ALGORITHM_VERSION,
    MIN_COMPONENT_COVERAGE_THRESHOLD,
    StrengthComponents,
)

DEFAULT_WEIGHTS = {
    "momentum": Decimal("0.30"),
    "breadth": Decimal("0.25"),
    "technical": Decimal("0.20"),
    "institutional": Decimal("0.15"),
    "turnover": Decimal("0.10"),
}


class IndustryStrengthScoringService:
    """Algorithm twml-industry-strength-v1 implementation for cross-sectional scoring."""

    def __init__(self, weights: dict[str, Decimal] | None = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS

    def calculate_percentile_scores(
        self, raw_values: list[tuple[any, Decimal]]
    ) -> dict[any, Decimal]:
        """Convert list of (key, raw_value) to deterministic percentile ranks 0..100.
        
        Key tie-breaking ensures stability.
        """
        if not raw_values:
            return {}
        if len(raw_values) == 1:
            return {raw_values[0][0]: Decimal("50.00")}

        # Sort by raw_value ascending, then key string representation for deterministic tie breaking
        sorted_items = sorted(raw_values, key=lambda x: (x[1], str(x[0])))
        n = len(sorted_items)
        result = {}
        for idx, (k, _) in enumerate(sorted_items):
            pct = (Decimal(str(idx)) / Decimal(str(n - 1))) * Decimal("100")
            result[k] = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return result

    def score_group(
        self,
        group_data: list[dict],
    ) -> list[dict]:
        """Given raw metric dicts for a single (trade_date, taxonomy_type, window) cross-section,
        calculate component scores, weighted strength_score, component_coverage, and rank.
        """
        if not group_data:
            return []

        # Extract raw metrics per component
        momentum_raw = []
        breadth_raw = []
        tech_raw = []
        inst_raw = []
        turnover_raw = []

        for item in group_data:
            key = item["taxonomy_id"]
            if item.get("equal_weight_return") is not None:
                momentum_raw.append((key, Decimal(str(item["equal_weight_return"]))))
            if item.get("advance_ratio") is not None:
                breadth_raw.append((key, Decimal(str(item["advance_ratio"]))))

            m20 = item.get("above_ma20_pct")
            m60 = item.get("above_ma60_pct")
            if m20 is not None and m60 is not None:
                avg_tech = (Decimal(str(m20)) + Decimal(str(m60))) / Decimal("2")
                tech_raw.append((key, avg_tech))

            f_net = item.get("foreign_net_amount") or Decimal("0")
            t_net = item.get("investment_trust_net_amount") or Decimal("0")
            d_net = item.get("dealer_net_amount") or Decimal("0")
            tot_inst = Decimal(str(f_net)) + Decimal(str(t_net)) + Decimal(str(d_net))
            inst_raw.append((key, tot_inst))

            if item.get("turnover_momentum") is not None:
                turnover_raw.append((key, Decimal(str(item["turnover_momentum"]))))

        momentum_pcts = self.calculate_percentile_scores(momentum_raw)
        breadth_pcts = self.calculate_percentile_scores(breadth_raw)
        tech_pcts = self.calculate_percentile_scores(tech_raw)
        inst_pcts = self.calculate_percentile_scores(inst_raw)
        turnover_pcts = self.calculate_percentile_scores(turnover_raw)

        results = []
        for item in group_data:
            k = item["taxonomy_id"]
            m_score = momentum_pcts.get(k)
            b_score = breadth_pcts.get(k)
            tc_score = tech_pcts.get(k)
            i_score = inst_pcts.get(k)
            to_score = turnover_pcts.get(k)

            component_scores = {
                "momentum": m_score,
                "breadth": b_score,
                "technical": tc_score,
                "institutional": i_score,
                "turnover": to_score,
            }

            available_weight = Decimal("0")
            weighted_sum = Decimal("0")

            for comp_name, weight in self.weights.items():
                val = component_scores.get(comp_name)
                if val is not None:
                    available_weight += weight
                    weighted_sum += val * weight

            component_coverage = available_weight.quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

            if component_coverage >= MIN_COMPONENT_COVERAGE_THRESHOLD and available_weight > 0:
                final_score = (weighted_sum / available_weight).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                final_score = None

            scored_item = dict(item)
            scored_item["components"] = StrengthComponents(
                momentum_score=m_score,
                breadth_score=b_score,
                technical_score=tc_score,
                institutional_score=i_score,
                turnover_score=to_score,
            )
            scored_item["strength_score"] = final_score
            scored_item["component_coverage"] = component_coverage
            scored_item["algorithm_version"] = ALGORITHM_VERSION
            results.append(scored_item)

        # Deterministic Ranking
        # Primary: strength_score DESC (nulls last)
        # Secondary: equal_weight_return DESC
        # Tertiary: taxonomy_code ASC, taxonomy_id ASC
        sorted_results = sorted(
            results,
            key=lambda x: (
                x["strength_score"] is None,
                -(x["strength_score"] if x["strength_score"] is not None else Decimal("-9999")),
                -(
                    x["equal_weight_return"]
                    if x.get("equal_weight_return") is not None
                    else Decimal("-9999")
                ),
                x.get("taxonomy_code", ""),
                str(x["taxonomy_id"]),
            ),
        )

        for idx, item in enumerate(sorted_results, start=1):
            item["rank"] = idx if item["strength_score"] is not None else None

        return sorted_results
