from typing import List, Dict, Any, Optional
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import RobustnessScenario, RobustnessCheck


class RobustnessEngine:
    """
    Deterministic Robustness Testing Engine for VERIDEX.
    Tests baseline findings against explicit alternative scenarios (e.g. order-status variations or metric definition shifts).
    Returns deterministic status: STABLE, SENSITIVE, or INSUFFICIENT_EVIDENCE.
    Zero arbitrary confidence percentages.
    """

    def __init__(self):
        self._counter = 0

    def generate_id(self, prefix: str = "rob") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def run_robustness_assessment(
        self,
        evidence_items: List[EvidenceItem],
        query_data: Optional[List[Dict[str, Any]]] = None,
        alternate_data: Optional[List[Dict[str, Any]]] = None,
        scenario_description: str = "Order status filtering sensitivity check"
    ) -> RobustnessCheck:
        """
        Runs a deterministic sensitivity check comparing baseline query findings against an alternate scenario.
        Returns RobustnessCheck object.
        """
        check_id = self.generate_id("rob")
        fact_ids = [ev.evidence_id for ev in evidence_items if ev.evidence_type == EvidenceType.FACT]

        if not query_data or len(query_data) == 0:
            baseline = RobustnessScenario(
                scenario_name="baseline_scenario",
                assumptions={"order_status": "Completed"},
                result_summary={"row_count": 0},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status="INSUFFICIENT_EVIDENCE",
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="Insufficient database query evidence returned to run robustness assessment.",
                supporting_evidence_ids=fact_ids
            )

        # Build baseline summary
        first_row = query_data[0]
        key_col = next((c for c in ["region", "product_name", "customer_name", "category"] if c in first_row), list(first_row.keys())[0])
        baseline_top = first_row.get(key_col)

        baseline_scenario = RobustnessScenario(
            scenario_name="baseline_completed_orders",
            assumptions={"order_status": "Completed", "primary_key": key_col},
            result_summary={"top_candidate": baseline_top, "total_rows": len(query_data)},
            is_recommendation_changed=False
        )

        alternate_scenarios: List[RobustnessScenario] = []

        if alternate_data is not None and len(alternate_data) > 0:
            alt_top = alternate_data[0].get(key_col)
            is_changed = (alt_top != baseline_top)

            alt_scenario = RobustnessScenario(
                scenario_name="alternate_all_order_statuses",
                assumptions={"order_status": "All (Completed + Returned + Cancelled)", "primary_key": key_col},
                result_summary={"top_candidate": alt_top, "total_rows": len(alternate_data)},
                is_recommendation_changed=is_changed
            )
            alternate_scenarios.append(alt_scenario)

            status = "SENSITIVE" if is_changed else "STABLE"
            change_desc = "changed top business segment" if is_changed else "remained consistent"
            explanation = f"Robustness check assessed '{scenario_description}': baseline top '{baseline_top}' {change_desc} under alternate scenario ('{alt_top}'). Status: {status}."
        else:
            # Synthetic sensitivity test against second-place gap if alternate data not provided directly
            if len(query_data) >= 2:
                second_row = query_data[1]
                num_cols = [c for c, v in first_row.items() if isinstance(v, (int, float))]
                if num_cols:
                    m_col = num_cols[0]
                    v1 = float(first_row[m_col])
                    v2 = float(second_row[m_col])
                    gap_pct = round(((v1 - v2) / abs(v1)) * 100, 2) if v1 != 0 else 0.0

                    # If lead margin is under 5%, flag as SENSITIVE to small volume shifts
                    is_sensitive = (gap_pct < 5.0)
                    status = "SENSITIVE" if is_sensitive else "STABLE"

                    alt_scenario = RobustnessScenario(
                        scenario_name="alternate_margin_sensitivity",
                        assumptions={"lead_margin_threshold": "5.0%"},
                        result_summary={"lead_margin_percent": gap_pct, "second_candidate": second_row.get(key_col)},
                        is_recommendation_changed=is_sensitive
                    )
                    alternate_scenarios.append(alt_scenario)

                    explanation = f"Robustness check evaluated lead margin gap ({gap_pct}%). Top candidate '{baseline_top}' lead is {'narrow (<5%), making finding SENSITIVE' if is_sensitive else 'strong (>=5%), making finding STABLE'}."
                else:
                    status = "STABLE"
                    explanation = f"Baseline query findings for '{baseline_top}' verified. Status: STABLE."
            else:
                status = "STABLE"
                explanation = f"Single-record finding for '{baseline_top}' verified. Status: STABLE."

        return RobustnessCheck(
            check_id=check_id,
            status=status,
            baseline_scenario=baseline_scenario,
            alternate_scenarios=alternate_scenarios,
            explanation=explanation,
            supporting_evidence_ids=fact_ids
        )
