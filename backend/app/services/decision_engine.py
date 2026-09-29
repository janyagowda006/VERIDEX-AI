from typing import List, Dict, Any, Optional
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import (
    DecisionCriterion,
    Recommendation,
    RobustnessCheck,
    DecisionAnalysis
)


class DecisionEngine:
    """
    Deterministic Decision Engine for VERIDEX.
    Evaluates business data against structured decision criteria, ranks candidates, and builds traceable recommendations.
    Core Principle: "AI for reasoning, code for correctness."
    """

    def __init__(self):
        self._counter = 0

    def generate_id(self, prefix: str = "dec") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def evaluate_criterion(
        self,
        criterion_name: str,
        metric_name: str,
        operator: str,
        threshold_value: Any,
        actual_value: Any
    ) -> DecisionCriterion:
        """
        Deterministically evaluates a criterion against an observed metric value.
        Supported operators: '>=', '<=', '==', '!=', '>', '<'
        """
        crit_id = self.generate_id("crit")
        is_met = False

        if actual_value is None or threshold_value is None:
            is_met = False
            expl = f"Criterion '{criterion_name}' could not be evaluated: actual or threshold value is missing."
        else:
            try:
                a_val = float(actual_value) if isinstance(actual_value, (int, float, str)) and str(actual_value).replace('.', '', 1).isdigit() else actual_value
                t_val = float(threshold_value) if isinstance(threshold_value, (int, float, str)) and str(threshold_value).replace('.', '', 1).isdigit() else threshold_value

                if operator == ">=":
                    is_met = bool(a_val >= t_val)
                elif operator == "<=":
                    is_met = bool(a_val <= t_val)
                elif operator == "==":
                    is_met = bool(a_val == t_val)
                elif operator == "!=":
                    is_met = bool(a_val != t_val)
                elif operator == ">":
                    is_met = bool(a_val > t_val)
                elif operator == "<":
                    is_met = bool(a_val < t_val)
                else:
                    is_met = False
                    expl = f"Unsupported operator '{operator}' for criterion evaluation."

                status_str = "satisfied" if is_met else "not satisfied"
                expl = f"Criterion '{criterion_name}' was {status_str}: {metric_name} actual value ({actual_value}) {operator} threshold ({threshold_value})."
            except Exception as e:
                is_met = False
                expl = f"Error evaluating criterion '{criterion_name}': {str(e)}"

        return DecisionCriterion(
            criterion_id=crit_id,
            criterion_name=criterion_name,
            metric_name=metric_name,
            operator=operator,
            threshold_value=threshold_value,
            actual_value=actual_value,
            is_met=is_met,
            explanation=expl
        )

    def rank_candidates(
        self,
        data: List[Dict[str, Any]],
        key_col: str,
        metric_col: str,
        top_n: int = 5,
        ascending: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Deterministically ranks data records based on a metric column.
        """
        if not data or not metric_col:
            return []

        def get_sort_key(row):
            val = row.get(metric_col)
            if val is None:
                return float('-inf') if not ascending else float('inf')
            try:
                return float(val)
            except Exception:
                return str(val)

        sorted_rows = sorted(data, key=get_sort_key, reverse=not ascending)
        rankings = []
        for idx, row in enumerate(sorted_rows[:top_n], start=1):
            rankings.append({
                "rank": idx,
                key_col: row.get(key_col, f"Item {idx}"),
                metric_col: row.get(metric_col),
                "details": row
            })
        return rankings

    def build_recommendation(
        self,
        action_title: str,
        rationale: str,
        supporting_evidence_ids: List[str],
        robustness_status: str,
        relevant_claim_ids: Optional[List[str]] = None,
        limitations: Optional[List[str]] = None
    ) -> Recommendation:
        """
        Constructs a structured action recommendation linked to evidence IDs and robustness status.
        """
        rec_id = self.generate_id("rec")
        return Recommendation(
            recommendation_id=rec_id,
            action_title=action_title,
            rationale=rationale,
            supporting_evidence_ids=supporting_evidence_ids or [],
            relevant_claim_ids=relevant_claim_ids or [],
            limitations=limitations or [],
            robustness_status=robustness_status
        )

    def analyze_decision(
        self,
        question: str,
        evidence_items: List[EvidenceItem],
        query_data: Optional[List[Dict[str, Any]]] = None,
        robustness: Optional[RobustnessCheck] = None
    ) -> DecisionAnalysis:
        """
        Main decision intelligence synthesis function.
        Generates criteria evaluations, rankings, and actionable recommendation from verified evidence.
        """
        anal_id = self.generate_id("anal")
        criteria: List[DecisionCriterion] = []
        rankings: List[Dict[str, Any]] = []

        fact_ids = [ev.evidence_id for ev in evidence_items if ev.evidence_type == EvidenceType.FACT]
        rob_status = robustness.status if robustness else "INSUFFICIENT_EVIDENCE"

        if query_data and len(query_data) > 0:
            first_row = query_data[0]
            # Identify primary entity key and metric column
            key_col = next((c for c in ["region", "product_name", "customer_name", "category"] if c in first_row), list(first_row.keys())[0])
            num_cols = [c for c, v in first_row.items() if isinstance(v, (int, float))]

            if num_cols:
                metric_col = num_cols[0]
                rankings = self.rank_candidates(query_data, key_col=key_col, metric_col=metric_col, top_n=5)

                top_candidate = rankings[0] if rankings else None
                top_val = top_candidate.get(metric_col) if top_candidate else 0.0

                crit = self.evaluate_criterion(
                    criterion_name=f"Top {key_col.capitalize()} Value Evaluation",
                    metric_name=metric_col,
                    operator=">",
                    threshold_value=0.0,
                    actual_value=top_val
                )
                criteria.append(crit)

                action_title = f"Prioritize {key_col.capitalize()} '{top_candidate[key_col]}'" if top_candidate else "Investigate top business segment"
                rationale = f"Observed top performance in '{top_candidate[key_col]}' with {metric_col} = {top_val} based on verified database evidence." if top_candidate else "Database query returned metrics."

                rec = self.build_recommendation(
                    action_title=action_title,
                    rationale=rationale,
                    supporting_evidence_ids=fact_ids,
                    robustness_status=rob_status
                )
            else:
                rec = self.build_recommendation(
                    action_title="Review query data findings",
                    rationale="Database query returned non-numeric query records.",
                    supporting_evidence_ids=fact_ids,
                    robustness_status=rob_status
                )
        else:
            rec = self.build_recommendation(
                action_title="Gather additional data",
                rationale="Insufficient database evidence returned to formulate a specific recommendation.",
                supporting_evidence_ids=fact_ids,
                robustness_status="INSUFFICIENT_EVIDENCE"
            )

        summary = f"Decision analysis evaluated {len(criteria)} criteria and produced rankings for {len(rankings)} candidates with robustness status '{rob_status}'."

        return DecisionAnalysis(
            analysis_id=anal_id,
            summary=summary,
            criteria_evaluated=criteria,
            rankings=rankings,
            recommendation=rec,
            robustness=robustness
        )
