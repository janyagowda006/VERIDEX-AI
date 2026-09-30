import math
from typing import List, Dict, Any, Optional
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import RobustnessScenario, RobustnessCheck

# Explicit default threshold constants
DEFAULT_MARGIN_SENSITIVITY_THRESHOLD_PCT: float = 5.0
DEFAULT_SCENARIO_THRESHOLD_PCT: float = 5.0
DEFAULT_OUTLIER_THRESHOLD_PCT: float = 10.0

ROBUSTNESS_STATUS_STABLE = "STABLE"
ROBUSTNESS_STATUS_SENSITIVE = "SENSITIVE"
ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def _is_valid_threshold(val: Any) -> bool:
    """Validates that a threshold is a finite, non-negative real number."""
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        f_val = float(val)
        return math.isfinite(f_val) and f_val >= 0.0
    except (ValueError, TypeError, OverflowError):
        return False


def _is_valid_finite_number(val: Any) -> bool:
    """Validates that a value is a valid, finite real number (not None, bool, str, NaN, or inf)."""
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(float(val))
    except (ValueError, TypeError, OverflowError):
        return False


def _safe_float(val: Any) -> Optional[float]:
    """Safely converts a value to float if valid and finite, else returns None."""
    if _is_valid_finite_number(val):
        return float(val)
    return None


class RobustnessEngine:
    """
    Deterministic Robustness Testing Engine for VERIDEX.
    Tests baseline findings against explicit alternative scenarios and evaluates outlier sensitivity.
    Returns deterministic status: STABLE, SENSITIVE, or INSUFFICIENT_EVIDENCE.
    Zero arbitrary confidence percentages. Pure Python calculations with strict finite numeric guards.
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
        scenario_description: str = "Order status filtering sensitivity check",
        alternate_scenarios: Optional[List[Dict[str, Any]]] = None,
        sensitivity_threshold_pct: float = DEFAULT_MARGIN_SENSITIVITY_THRESHOLD_PCT
    ) -> RobustnessCheck:
        """
        Runs a deterministic sensitivity check comparing baseline query findings against
        an alternate scenario or explicit multi-scenario definitions.
        Preserves backward compatibility with Phase 6 call signatures.
        """
        check_id = self.generate_id("rob")
        fact_ids = [ev.evidence_id for ev in evidence_items if ev.evidence_type == EvidenceType.FACT]

        # Validate threshold
        if not _is_valid_threshold(sensitivity_threshold_pct):
            baseline = RobustnessScenario(
                scenario_name="baseline_scenario",
                assumptions={"sensitivity_threshold_pct": str(sensitivity_threshold_pct)},
                result_summary={"error": "Invalid threshold value"},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation=f"Invalid sensitivity_threshold_pct '{sensitivity_threshold_pct}': threshold must be a finite, non-negative number.",
                supporting_evidence_ids=fact_ids
            )

        if not isinstance(query_data, list) or len(query_data) == 0 or not isinstance(query_data[0], dict) or not query_data[0]:
            baseline = RobustnessScenario(
                scenario_name="baseline_scenario",
                assumptions={"order_status": "Completed"},
                result_summary={"row_count": len(query_data) if isinstance(query_data, list) else 0},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="Insufficient database query evidence returned to run robustness assessment.",
                supporting_evidence_ids=fact_ids
            )

        # Multi-scenario path if explicitly supplied
        if alternate_scenarios is not None and len(alternate_scenarios) > 0:
            return self.evaluate_multi_scenario_robustness(
                baseline_data=query_data,
                scenarios=alternate_scenarios,
                evidence_items=evidence_items,
                threshold_pct=sensitivity_threshold_pct,
                scenario_description=scenario_description
            )

        # Build baseline summary
        first_row = query_data[0]
        key_col = next((c for c in ["candidate_id", "candidate", "name", "id", "region", "product_name", "customer_name", "category"] if c in first_row), list(first_row.keys())[0])
        baseline_top = first_row.get(key_col)

        baseline_scenario = RobustnessScenario(
            scenario_name="baseline_completed_orders",
            assumptions={"order_status": "Completed", "primary_key": key_col},
            result_summary={"top_candidate": baseline_top, "total_rows": len(query_data)},
            is_recommendation_changed=False
        )

        alt_scenarios_list: List[RobustnessScenario] = []

        if alternate_data is not None and len(alternate_data) > 0:
            if not isinstance(alternate_data, list) or not isinstance(alternate_data[0], dict):
                return RobustnessCheck(
                    check_id=check_id,
                    status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                    baseline_scenario=baseline_scenario,
                    alternate_scenarios=[],
                    explanation="Invalid alternate data format: expected list of dictionaries.",
                    supporting_evidence_ids=fact_ids
                )
            alt_top = alternate_data[0].get(key_col)
            is_changed = (alt_top != baseline_top)

            alt_scenario = RobustnessScenario(
                scenario_name="alternate_all_order_statuses",
                assumptions={"order_status": "All (Completed + Returned + Cancelled)", "primary_key": key_col},
                result_summary={"top_candidate": alt_top, "total_rows": len(alternate_data)},
                is_recommendation_changed=is_changed
            )
            alt_scenarios_list.append(alt_scenario)

            status = ROBUSTNESS_STATUS_SENSITIVE if is_changed else ROBUSTNESS_STATUS_STABLE
            change_desc = "changed top business segment" if is_changed else "remained consistent"
            explanation = f"Robustness check assessed '{scenario_description}': baseline top '{baseline_top}' {change_desc} under alternate scenario ('{alt_top}'). Status: {status}."
        else:
            # Synthetic sensitivity test against second-place gap if alternate data not provided directly
            if len(query_data) >= 2:
                second_row = query_data[1]
                if not isinstance(second_row, dict):
                    return RobustnessCheck(
                        check_id=check_id,
                        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                        baseline_scenario=baseline_scenario,
                        alternate_scenarios=[],
                        explanation="Invalid query data: expected row dictionary.",
                        supporting_evidence_ids=fact_ids
                    )
                candidate_cols = [c for c in first_row.keys() if c != key_col]
                m_col = None
                for c in candidate_cols:
                    if _is_valid_finite_number(first_row.get(c)) or _is_valid_finite_number(second_row.get(c)):
                        m_col = c
                        break
                if not m_col and candidate_cols:
                    m_col = candidate_cols[0]

                if m_col:
                    v1_raw = first_row.get(m_col)
                    v2_raw = second_row.get(m_col)

                    if not _is_valid_finite_number(v1_raw) or not _is_valid_finite_number(v2_raw):
                        return RobustnessCheck(
                            check_id=check_id,
                            status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                            baseline_scenario=baseline_scenario,
                            alternate_scenarios=[],
                            explanation="Invalid non-numeric or non-finite metric values in query data.",
                            supporting_evidence_ids=fact_ids
                        )

                    v1 = float(v1_raw)
                    v2 = float(v2_raw)
                    if v1 == 0.0:
                        return RobustnessCheck(
                            check_id=check_id,
                            status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                            baseline_scenario=baseline_scenario,
                            alternate_scenarios=[],
                            explanation="Baseline top candidate metric is zero; lead margin percentage is undefined.",
                            supporting_evidence_ids=fact_ids
                        )

                    gap_pct = round(((v1 - v2) / abs(v1)) * 100, 2)
                    is_sensitive = (gap_pct < sensitivity_threshold_pct)
                    status = ROBUSTNESS_STATUS_SENSITIVE if is_sensitive else ROBUSTNESS_STATUS_STABLE

                    alt_scenario = RobustnessScenario(
                        scenario_name="alternate_margin_sensitivity",
                        assumptions={"lead_margin_threshold": f"{sensitivity_threshold_pct}%"},
                        result_summary={"lead_margin_percent": gap_pct, "second_candidate": second_row.get(key_col)},
                        is_recommendation_changed=is_sensitive
                    )
                    alt_scenarios_list.append(alt_scenario)

                    explanation = f"Robustness check evaluated lead margin gap ({gap_pct}%). Top candidate '{baseline_top}' lead is {'narrow (<' + str(sensitivity_threshold_pct) + '%), making finding SENSITIVE' if is_sensitive else 'strong (>=' + str(sensitivity_threshold_pct) + '%), making finding STABLE'}."
                else:
                    status = ROBUSTNESS_STATUS_STABLE
                    explanation = f"Baseline query findings for '{baseline_top}' verified. Status: STABLE."
            else:
                status = ROBUSTNESS_STATUS_STABLE
                explanation = f"Single-record finding for '{baseline_top}' verified. Status: STABLE."

        return RobustnessCheck(
            check_id=check_id,
            status=status,
            baseline_scenario=baseline_scenario,
            alternate_scenarios=alt_scenarios_list,
            explanation=explanation,
            supporting_evidence_ids=fact_ids
        )

    def evaluate_multi_scenario_robustness(
        self,
        baseline_data: List[Dict[str, Any]],
        scenarios: List[Dict[str, Any]],
        evidence_items: Optional[List[EvidenceItem]] = None,
        key_col: Optional[str] = None,
        metric_col: Optional[str] = None,
        threshold_pct: float = DEFAULT_SCENARIO_THRESHOLD_PCT,
        scenario_description: str = "Multi-scenario sensitivity evaluation"
    ) -> RobustnessCheck:
        """
        Deterministically evaluates multiple explicitly supplied alternate scenarios against baseline data.
        Supported scenario representations:
        - Explicit dataset: {"name": str, "data": List[Dict[str, Any]]}
        - Metric adjustments: {"name": str, "adjustments": Dict[str, float]} (e.g. {"revenue": -10.0})
        - Pre-evaluated summary: {"name": str, "result_summary": Dict[str, Any], "is_recommendation_changed": bool}

        Deterministic Threshold Rule:
        A scenario triggers SENSITIVE classification if:
        1. The top candidate changes (alt_top != baseline_top), OR
        2. Where the scenario metric is comparable, the percentage metric shift exceeds threshold_pct:
           abs((alt_metric - baseline_metric) / baseline_metric) * 100 >= threshold_pct.
        If non-numeric, NaN, infinite, or invalid inputs are encountered, status is INSUFFICIENT_EVIDENCE.
        """
        check_id = self.generate_id("rob")
        fact_ids = [ev.evidence_id for ev in (evidence_items or []) if ev.evidence_type == EvidenceType.FACT]

        # 1. Validate threshold
        if not _is_valid_threshold(threshold_pct):
            baseline = RobustnessScenario(
                scenario_name="baseline_scenario",
                assumptions={"threshold_pct": str(threshold_pct)},
                result_summary={"error": "Invalid threshold value"},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation=f"Invalid threshold_pct '{threshold_pct}': threshold must be a finite, non-negative number.",
                supporting_evidence_ids=fact_ids
            )

        # 2. Validate baseline data
        if not isinstance(baseline_data, list) or len(baseline_data) == 0:
            baseline = RobustnessScenario(
                scenario_name="baseline_scenario",
                assumptions={"row_count": len(baseline_data) if isinstance(baseline_data, list) else 0},
                result_summary={"error": "Empty or invalid baseline data"},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="Insufficient database query evidence returned to run multi-scenario robustness assessment.",
                supporting_evidence_ids=fact_ids
            )

        for r in baseline_data:
            if not isinstance(r, dict):
                baseline = RobustnessScenario(
                    scenario_name="baseline_scenario",
                    assumptions={"error": "invalid_row_type"},
                    result_summary={"error": f"Invalid row type: {type(r).__name__}"},
                    is_recommendation_changed=False
                )
                return RobustnessCheck(
                    check_id=check_id,
                    status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                    baseline_scenario=baseline,
                    alternate_scenarios=[],
                    explanation=f"Baseline data rows must be dictionaries, got {type(r).__name__}.",
                    supporting_evidence_ids=fact_ids
                )

        first_row = baseline_data[0]
        if not first_row:
            baseline = RobustnessScenario(
                scenario_name="baseline_scenario",
                assumptions={"error": "empty_first_row"},
                result_summary={"error": "Empty first record in baseline data"},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="Baseline data contains empty records.",
                supporting_evidence_ids=fact_ids
            )

        # 3. Validate scenarios list
        if not isinstance(scenarios, list) or len(scenarios) == 0:
            baseline = RobustnessScenario(
                scenario_name="baseline_scenario",
                assumptions={"row_count": len(baseline_data)},
                result_summary={"total_records": len(baseline_data)},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="No alternate scenarios supplied for multi-scenario evaluation.",
                supporting_evidence_ids=fact_ids
            )

        eff_key = key_col or next((c for c in ["candidate_id", "candidate", "name", "id", "region", "product_name", "customer_name", "category"] if c in first_row), list(first_row.keys())[0])

        if metric_col:
            eff_metric = metric_col
        else:
            # Check non-key columns across baseline rows and scenario data
            candidate_metrics = [c for c in first_row.keys() if c != eff_key]
            eff_metric = None
            for c in candidate_metrics:
                is_num_in_baseline = any(isinstance(r.get(c), (int, float)) for r in baseline_data if isinstance(r, dict))
                is_num_in_scenario = any(
                    isinstance(r.get(c), (int, float))
                    for sc in scenarios if isinstance(sc, dict) and "data" in sc and isinstance(sc.get("data"), list)
                    for r in sc["data"] if isinstance(r, dict)
                )
                has_adj_in_scenario = any(
                    isinstance(sc, dict) and "adjustments" in sc and isinstance(sc.get("adjustments"), dict) and c in sc["adjustments"]
                    for sc in scenarios
                )
                if is_num_in_baseline or is_num_in_scenario or has_adj_in_scenario:
                    eff_metric = c
                    break

            if not eff_metric and candidate_metrics:
                eff_metric = candidate_metrics[0]

        # Validate that baseline metric values are valid finite numbers if metric column is present
        if eff_metric:
            for r in baseline_data:
                val = r.get(eff_metric)
                if not _is_valid_finite_number(val):
                    baseline = RobustnessScenario(
                        scenario_name="baseline_scenario",
                        assumptions={"primary_key": eff_key, "metric": eff_metric},
                        result_summary={"error": f"Invalid non-numeric or non-finite metric value: {val}"},
                        is_recommendation_changed=False
                    )
                    return RobustnessCheck(
                        check_id=check_id,
                        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                        baseline_scenario=baseline,
                        alternate_scenarios=[],
                        explanation=f"Invalid non-numeric or non-finite metric value '{val}' detected in baseline data.",
                        supporting_evidence_ids=fact_ids
                    )

            sorted_baseline = sorted(baseline_data, key=lambda r: float(r[eff_metric]), reverse=True)
            baseline_top = sorted_baseline[0].get(eff_key)
            baseline_val = float(sorted_baseline[0][eff_metric])
        else:
            sorted_baseline = list(baseline_data)
            baseline_top = sorted_baseline[0].get(eff_key)
            baseline_val = None

        baseline_scenario = RobustnessScenario(
            scenario_name="baseline_scenario",
            assumptions={"primary_key": eff_key, "metric": eff_metric, "threshold_pct": threshold_pct, "total_records": len(baseline_data)},
            result_summary={"top_candidate": baseline_top, "metric_value": baseline_val},
            is_recommendation_changed=False
        )

        alt_scenarios_list: List[RobustnessScenario] = []

        for idx, sc in enumerate(scenarios, start=1):
            if not isinstance(sc, dict):
                return RobustnessCheck(
                    check_id=check_id,
                    status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                    baseline_scenario=baseline_scenario,
                    alternate_scenarios=[],
                    explanation=f"Scenario entries must be dictionaries, got {type(sc).__name__}.",
                    supporting_evidence_ids=fact_ids
                )
            sc_name = sc.get("scenario_name") or sc.get("name") or f"scenario_{idx}"
            sc_assumptions = dict(sc.get("assumptions") or {})
            sc_assumptions["threshold_pct"] = threshold_pct

            # Case A: Explicit alternate data rows
            if "data" in sc:
                sc_data = sc["data"]
                if not isinstance(sc_data, list) or len(sc_data) == 0:
                    return RobustnessCheck(
                        check_id=check_id,
                        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                        baseline_scenario=baseline_scenario,
                        alternate_scenarios=[],
                        explanation=f"Scenario '{sc_name}' contains empty or invalid data rows.",
                        supporting_evidence_ids=fact_ids
                    )

                for row in sc_data:
                    if not isinstance(row, dict):
                        return RobustnessCheck(
                            check_id=check_id,
                            status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                            baseline_scenario=baseline_scenario,
                            alternate_scenarios=[],
                            explanation=f"Scenario '{sc_name}' contains invalid non-dict row: {row}.",
                            supporting_evidence_ids=fact_ids
                        )
                if eff_metric:
                    for row in sc_data:
                        v = row.get(eff_metric)
                        if not _is_valid_finite_number(v):
                            return RobustnessCheck(
                                check_id=check_id,
                                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                                baseline_scenario=baseline_scenario,
                                alternate_scenarios=[],
                                explanation=f"Invalid non-numeric or non-finite metric value '{v}' in scenario '{sc_name}'.",
                                supporting_evidence_ids=fact_ids
                            )
                    sorted_alt = sorted(sc_data, key=lambda r: float(r[eff_metric]), reverse=True)
                    alt_top = sorted_alt[0].get(eff_key) if sorted_alt else None
                    alt_val = float(sorted_alt[0][eff_metric]) if sorted_alt else None
                else:
                    sorted_alt = list(sc_data)
                    alt_top = sorted_alt[0].get(eff_key) if sorted_alt else None
                    alt_val = None

            # Case B: Adjustments applied to baseline data
            elif "adjustments" in sc:
                adjs = sc["adjustments"]
                if not isinstance(adjs, dict):
                    return RobustnessCheck(
                        check_id=check_id,
                        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                        baseline_scenario=baseline_scenario,
                        alternate_scenarios=[],
                        explanation=f"Scenario '{sc_name}' adjustments must be a dictionary.",
                        supporting_evidence_ids=fact_ids
                    )

                for k, adj_v in adjs.items():
                    if not _is_valid_finite_number(adj_v):
                        return RobustnessCheck(
                            check_id=check_id,
                            status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                            baseline_scenario=baseline_scenario,
                            alternate_scenarios=[],
                            explanation=f"Invalid non-numeric or non-finite adjustment '{adj_v}' for '{k}' in scenario '{sc_name}'.",
                            supporting_evidence_ids=fact_ids
                        )

                sc_assumptions.update(adjs)
                adjusted_rows = []
                for row in baseline_data:
                    new_row = dict(row)
                    if eff_metric and eff_metric in adjs:
                        pct = float(adjs[eff_metric])
                        curr_v = float(new_row[eff_metric])
                        new_row[eff_metric] = round(curr_v * (1.0 + pct / 100.0), 4)
                    entity_val = str(new_row.get(eff_key))
                    if entity_val in adjs and eff_metric:
                        pct = float(adjs[entity_val])
                        curr_v = float(new_row[eff_metric])
                        new_row[eff_metric] = round(curr_v * (1.0 + pct / 100.0), 4)
                    adjusted_rows.append(new_row)

                if eff_metric:
                    sorted_alt = sorted(adjusted_rows, key=lambda r: float(r[eff_metric]), reverse=True)
                    alt_top = sorted_alt[0].get(eff_key) if sorted_alt else None
                    alt_val = float(sorted_alt[0][eff_metric]) if sorted_alt else None
                else:
                    sorted_alt = adjusted_rows
                    alt_top = sorted_alt[0].get(eff_key) if sorted_alt else None
                    alt_val = None

            # Case C: Pre-evaluated summary
            else:
                res_sum = sc.get("result_summary", {})
                if not isinstance(res_sum, dict):
                    return RobustnessCheck(
                        check_id=check_id,
                        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                        baseline_scenario=baseline_scenario,
                        alternate_scenarios=[],
                        explanation=f"Scenario '{sc_name}' result_summary must be a dictionary.",
                        supporting_evidence_ids=fact_ids
                    )
                alt_top = res_sum.get("top_candidate")
                raw_mv = res_sum.get("metric_value")
                if raw_mv is not None and not _is_valid_finite_number(raw_mv):
                    return RobustnessCheck(
                        check_id=check_id,
                        status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                        baseline_scenario=baseline_scenario,
                        alternate_scenarios=[],
                        explanation=f"Invalid non-numeric or non-finite metric_value '{raw_mv}' in scenario '{sc_name}'.",
                        supporting_evidence_ids=fact_ids
                    )
                alt_val = _safe_float(raw_mv)

            # Deterministic Threshold & Ranking Rule Evaluation
            candidate_changed = bool(alt_top is not None and baseline_top is not None and alt_top != baseline_top)

            if baseline_val is not None and alt_val is not None and baseline_val != 0.0:
                metric_shift_pct = round(((alt_val - baseline_val) / abs(baseline_val)) * 100, 2)
                metric_exceeded_threshold = bool(abs(metric_shift_pct) >= threshold_pct)
            else:
                metric_shift_pct = None
                metric_exceeded_threshold = False

            # Sensitivity determination: recommendation change OR metric exceeded threshold
            is_scenario_sensitive = candidate_changed or metric_exceeded_threshold
            if "is_recommendation_changed" in sc and not ("data" in sc or "adjustments" in sc):
                is_scenario_sensitive = bool(sc["is_recommendation_changed"])

            summary = {
                "top_candidate": alt_top,
                "metric_value": alt_val,
                "metric_shift_percent": metric_shift_pct,
                "threshold_pct": threshold_pct,
                "candidate_changed": candidate_changed,
                "metric_exceeded_threshold": metric_exceeded_threshold
            }

            alt_scenario = RobustnessScenario(
                scenario_name=sc_name,
                assumptions=sc_assumptions,
                result_summary=summary,
                is_recommendation_changed=is_scenario_sensitive
            )
            alt_scenarios_list.append(alt_scenario)

        changed_scenarios = [s.scenario_name for s in alt_scenarios_list if s.is_recommendation_changed]
        is_sensitive = len(changed_scenarios) > 0
        status = ROBUSTNESS_STATUS_SENSITIVE if is_sensitive else ROBUSTNESS_STATUS_STABLE

        if is_sensitive:
            explanation = (
                f"{scenario_description} (threshold={threshold_pct}%): finding changed or exceeded threshold under "
                f"{len(changed_scenarios)} of {len(alt_scenarios_list)} alternate scenario(s) "
                f"({', '.join(changed_scenarios)}). Status: SENSITIVE."
            )
        else:
            explanation = (
                f"{scenario_description} (threshold={threshold_pct}%): baseline top candidate '{baseline_top}' "
                f"remained consistent and metric shifts stayed within {threshold_pct}% across all "
                f"{len(alt_scenarios_list)} alternate scenario(s). Status: STABLE."
            )

        return RobustnessCheck(
            check_id=check_id,
            status=status,
            baseline_scenario=baseline_scenario,
            alternate_scenarios=alt_scenarios_list,
            explanation=explanation,
            supporting_evidence_ids=fact_ids
        )

    def evaluate_outlier_sensitivity(
        self,
        values: List[Any],
        metric_type: str = "mean",
        threshold_pct: float = DEFAULT_OUTLIER_THRESHOLD_PCT,
        labels: Optional[List[str]] = None,
        evidence_items: Optional[List[EvidenceItem]] = None,
        metric_name: str = "metric"
    ) -> RobustnessCheck:
        """
        Deterministically evaluates whether individual observations materially influence a summary metric
        using leave-one-out (jackknife) sensitivity analysis.
        Threshold rule: an observation is an influential outlier if its omission alters the baseline metric by >= threshold_pct.

        Classification:
        - SENSITIVE: >= 1 observation alters the metric by >= threshold_pct.
        - STABLE: no observation alters the metric by >= threshold_pct.
        - INSUFFICIENT_EVIDENCE: empty input, < 2 observations, non-finite values (NaN/inf), invalid types,
          or baseline metric == 0 (since percentage change is undefined).
        """
        check_id = self.generate_id("rob")
        fact_ids = [ev.evidence_id for ev in (evidence_items or []) if ev.evidence_type == EvidenceType.FACT]

        # 1. Validate threshold
        if not _is_valid_threshold(threshold_pct):
            baseline = RobustnessScenario(
                scenario_name="baseline_all_observations",
                assumptions={"threshold_pct": str(threshold_pct)},
                result_summary={"error": "Invalid threshold value"},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation=f"Invalid threshold_pct '{threshold_pct}': threshold must be a finite, non-negative number.",
                supporting_evidence_ids=fact_ids
            )

        # 2. Empty input handling
        if values is None or len(values) == 0:
            baseline = RobustnessScenario(
                scenario_name="baseline_all_observations",
                assumptions={"count": 0, "metric_type": metric_type},
                result_summary={"error": "Empty observation list"},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="Insufficient data: input observation list is empty.",
                supporting_evidence_ids=fact_ids
            )

        # 3. Explicit non-numeric and non-finite (NaN / inf) validation
        invalid_items = [v for v in values if not _is_valid_finite_number(v)]
        if invalid_items:
            baseline = RobustnessScenario(
                scenario_name="baseline_all_observations",
                assumptions={"count": len(values), "invalid_sample": [str(x) for x in invalid_items[:5]]},
                result_summary={"error": "Non-numeric or non-finite entries detected"},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation=f"Invalid non-numeric or non-finite observations detected in input: {invalid_items[:5]}. Outlier sensitivity cannot be calculated.",
                supporting_evidence_ids=fact_ids
            )

        # 4. Single-value input handling
        if len(values) < 2:
            baseline = RobustnessScenario(
                scenario_name="baseline_all_observations",
                assumptions={"count": len(values), "metric_type": metric_type},
                result_summary={"value": float(values[0])},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="Insufficient data: at least 2 observations are required to perform leave-one-out outlier sensitivity analysis.",
                supporting_evidence_ids=fact_ids
            )

        num_vals = [float(v) for v in values]
        n = len(num_vals)

        def _calc_metric(nums: List[float], m_type: str) -> float:
            if m_type == "sum":
                return sum(nums)
            elif m_type == "median":
                s = sorted(nums)
                mid = len(s) // 2
                return s[mid] if len(s) % 2 == 1 else (s[mid - 1] + s[mid]) / 2.0
            else:  # default "mean"
                return sum(nums) / len(nums)

        baseline_metric = _calc_metric(num_vals, metric_type)

        # 5. Outlier Zero-Baseline Handling: percentage change is undefined when baseline is zero
        if baseline_metric == 0.0:
            baseline = RobustnessScenario(
                scenario_name="baseline_all_observations",
                assumptions={"total_observations": n, "metric_type": metric_type, "threshold_pct": threshold_pct},
                result_summary={"baseline_metric": 0.0, "total_count": n},
                is_recommendation_changed=False
            )
            return RobustnessCheck(
                check_id=check_id,
                status=ROBUSTNESS_STATUS_INSUFFICIENT_EVIDENCE,
                baseline_scenario=baseline,
                alternate_scenarios=[],
                explanation="Baseline metric is zero; percentage-based outlier sensitivity is undefined.",
                supporting_evidence_ids=fact_ids
            )

        baseline_scenario = RobustnessScenario(
            scenario_name="baseline_all_observations",
            assumptions={"total_observations": n, "metric_type": metric_type, "threshold_pct": threshold_pct},
            result_summary={"baseline_metric": round(baseline_metric, 4), "total_count": n},
            is_recommendation_changed=False
        )

        alt_scenarios_list: List[RobustnessScenario] = []
        influential_count = 0

        for i in range(n):
            sub_vals = num_vals[:i] + num_vals[i + 1:]
            sub_metric = _calc_metric(sub_vals, metric_type)

            shift_pct = round(((sub_metric - baseline_metric) / abs(baseline_metric)) * 100, 2)
            is_material = bool(abs(shift_pct) >= threshold_pct)
            if is_material:
                influential_count += 1

            obs_label = labels[i] if (labels and i < len(labels)) else f"observation_{i + 1}"

            alt_scenario = RobustnessScenario(
                scenario_name=f"exclude_{obs_label}",
                assumptions={"excluded_index": i, "excluded_value": num_vals[i], "identifier": obs_label},
                result_summary={
                    "metric_without_observation": round(sub_metric, 4),
                    "shift_percent": shift_pct,
                    "is_material_outlier": is_material
                },
                is_recommendation_changed=is_material
            )
            alt_scenarios_list.append(alt_scenario)

        status = ROBUSTNESS_STATUS_SENSITIVE if influential_count > 0 else ROBUSTNESS_STATUS_STABLE

        if status == ROBUSTNESS_STATUS_SENSITIVE:
            explanation = (
                f"Outlier sensitivity check (threshold={threshold_pct}%): detected {influential_count} influential "
                f"observation(s) out of {n} whose removal alters baseline {metric_type} ({round(baseline_metric, 4)}) "
                f"by >= {threshold_pct}%. Status: SENSITIVE."
            )
        else:
            explanation = (
                f"Outlier sensitivity check (threshold={threshold_pct}%): no single observation alters baseline "
                f"{metric_type} ({round(baseline_metric, 4)}) by >= {threshold_pct}%. Status: STABLE."
            )

        return RobustnessCheck(
            check_id=check_id,
            status=status,
            baseline_scenario=baseline_scenario,
            alternate_scenarios=alt_scenarios_list,
            explanation=explanation,
            supporting_evidence_ids=fact_ids
        )
