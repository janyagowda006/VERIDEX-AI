import math
from typing import List, Dict, Any, Optional, Tuple, Union
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.decision import (
    DecisionCriterion,
    Recommendation,
    RobustnessCheck,
    DecisionAnalysis
)


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
    if isinstance(val, str):
        try:
            f = float(val.strip())
            return f if math.isfinite(f) else None
        except (ValueError, TypeError, OverflowError):
            return None
    return None


def _safe_numeric_conversion(val: Any) -> Any:
    """Attempts to safely convert numeric-like values to float while preserving original non-numeric types."""
    f = _safe_float(val)
    return f if f is not None else val


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
        Supported operators: '>=', '<=', '==', '!=', '>', '<', 'top_n', 'maximize', 'minimize'
        """
        crit_id = self.generate_id("crit")
        is_met = False

        if actual_value is None or threshold_value is None:
            is_met = False
            expl = f"Criterion '{criterion_name}' could not be evaluated: actual or threshold value is missing."
        else:
            try:
                a_val = _safe_numeric_conversion(actual_value)
                t_val = _safe_numeric_conversion(threshold_value)
                op_clean = str(operator).strip().lower()

                if op_clean == ">=":
                    is_met = bool(a_val >= t_val)
                elif op_clean == "<=":
                    is_met = bool(a_val <= t_val)
                elif op_clean == "==":
                    is_met = bool(a_val == t_val)
                elif op_clean == "!=":
                    is_met = bool(a_val != t_val)
                elif op_clean == ">":
                    is_met = bool(a_val > t_val)
                elif op_clean == "<":
                    is_met = bool(a_val < t_val)
                elif op_clean == "top_n":
                    if isinstance(t_val, (int, float)) and isinstance(a_val, (int, float)):
                        is_met = bool(a_val <= t_val)
                    elif isinstance(threshold_value, (list, tuple, set)):
                        is_met = bool(actual_value in threshold_value)
                    else:
                        is_met = False
                elif op_clean in ["maximize", "max"]:
                    is_met = bool(a_val >= t_val) if isinstance(t_val, (int, float)) else True
                elif op_clean in ["minimize", "min"]:
                    is_met = bool(a_val <= t_val) if isinstance(t_val, (int, float)) else True
                else:
                    is_met = False
                    expl = f"Unsupported operator '{operator}' for criterion evaluation."
                    return DecisionCriterion(
                        criterion_id=crit_id,
                        criterion_name=criterion_name,
                        metric_name=metric_name,
                        operator=operator,
                        threshold_value=threshold_value,
                        actual_value=actual_value,
                        is_met=False,
                        explanation=expl
                    )

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

    def validate_weights(
        self,
        criteria: List[Dict[str, Any]],
        weights: Optional[Union[Dict[str, Any], List[Any]]] = None
    ) -> Tuple[bool, Optional[str], Dict[str, float]]:
        """
        Deterministically validates and normalizes criterion weights.
        Rejects negative, NaN, infinite, or non-numeric weights.
        Returns: (is_valid, error_message, normalized_weights_dict)
        Normalized weight formula: normalized_weight = weight / sum(all_valid_weights)
        """
        if not criteria or not isinstance(criteria, list) or len(criteria) == 0:
            return False, "Criteria list must be a non-empty list.", {}

        raw_weights: Dict[str, float] = {}

        for idx, crit in enumerate(criteria, start=1):
            if not isinstance(crit, dict):
                return False, f"Criterion at index {idx} must be a dictionary.", {}

            c_name = crit.get("name") or crit.get("criterion_name") or f"criterion_{idx}"
            m_name = crit.get("metric") or crit.get("metric_name")

            raw_w: Any = None
            if isinstance(weights, dict):
                if c_name in weights:
                    raw_w = weights[c_name]
                elif m_name and m_name in weights:
                    raw_w = weights[m_name]
                elif "weight" in crit:
                    raw_w = crit["weight"]
                else:
                    raw_w = 1.0
            elif isinstance(weights, (list, tuple)):
                if len(weights) != len(criteria):
                    return False, f"Weights list length ({len(weights)}) does not match criteria count ({len(criteria)}).", {}
                raw_w = weights[idx - 1]
            else:
                raw_w = crit.get("weight", 1.0)

            # Strict validation: reject None, bool, str, NaN, inf, or negative
            if raw_w is None or isinstance(raw_w, bool) or not isinstance(raw_w, (int, float)):
                return False, f"Invalid non-numeric weight '{raw_w}' for criterion '{c_name}': weights must be finite real numbers.", {}

            try:
                f_w = float(raw_w)
                if not math.isfinite(f_w):
                    return False, f"Invalid non-finite weight '{raw_w}' for criterion '{c_name}': NaN and +/-infinity are rejected.", {}
                if f_w < 0.0:
                    return False, f"Invalid negative weight '{raw_w}' for criterion '{c_name}': weights must be non-negative.", {}
                raw_weights[c_name] = f_w
            except (ValueError, TypeError, OverflowError):
                return False, f"Invalid weight value '{raw_w}' for criterion '{c_name}'.", {}

        total_weight = sum(raw_weights.values())
        if total_weight == 0.0:
            return False, "Total weight is zero; cannot calculate weighted scores.", {}

        # Deterministic normalization: normalized_weight = raw_weight / sum(weights)
        norm_weights = {name: round(w / total_weight, 6) for name, w in raw_weights.items()}
        return True, None, norm_weights

    def rank_candidates(
        self,
        data: List[Dict[str, Any]],
        key_col: str,
        metric_col: str,
        top_n: int = 5,
        ascending: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Deterministically ranks data records based on a single metric column.
        Preserves backward compatibility with Phase 6 / 7A / 7B callers.
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

    def rank_candidates_multi_criteria(
        self,
        candidates: List[Dict[str, Any]],
        criteria: List[Dict[str, Any]],
        weights: Optional[Union[Dict[str, Any], List[Any]]] = None,
        key_col: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Deterministically evaluates and ranks candidates across multiple weighted criteria.

        Deterministic Scoring Model:
        - Maximize direction: norm_score = (val - min_val) / (max_val - min_val)
        - Minimize direction: norm_score = (max_val - val) / (max_val - min_val)
        - Threshold direction: norm_score = 1.0 if condition is satisfied else 0.0
        - If all candidate values are equal, norm_score = 1.0
        - Candidate total score = sum(norm_score_k * normalized_weight_k)
        - Tie-breaking: 1) total_score descending, 2) candidate_id string ascending, 3) original index ascending
        """
        if not candidates or not isinstance(candidates, list) or len(candidates) == 0:
            return []
        if not criteria or not isinstance(criteria, list) or len(criteria) == 0:
            return []

        is_valid, err_msg, norm_weights = self.validate_weights(criteria, weights)
        if not is_valid:
            return []

        first_cand = candidates[0] if isinstance(candidates[0], dict) else {}
        resolved_key = key_col or next((c for c in ["candidate_id", "candidate", "name", "id", "region", "product_name", "customer_name", "category", "item"] if c in first_cand), list(first_cand.keys())[0] if first_cand else "candidate")

        # Step 1: Pre-calculate min/max bounds for maximize and minimize criteria
        criteria_meta: List[Dict[str, Any]] = []
        for idx, crit in enumerate(criteria, start=1):
            c_name = crit.get("name") or crit.get("criterion_name") or f"criterion_{idx}"
            m_name = crit.get("metric") or crit.get("metric_name")
            direction_raw = str(crit.get("direction") or "").strip().lower()
            operator_raw = str(crit.get("operator") or "").strip().lower()

            if direction_raw in ["maximize", "max"] or operator_raw in ["maximize", "max"]:
                mode = "maximize"
            elif direction_raw in ["minimize", "min"] or operator_raw in ["minimize", "min"]:
                mode = "minimize"
            else:
                mode = "threshold"

            # Pool values for continuous min-max normalization
            valid_pool_vals: List[float] = []
            if mode in ["maximize", "minimize"] and m_name:
                for c in candidates:
                    if isinstance(c, dict):
                        v = c.get(m_name)
                        if _is_valid_finite_number(v):
                            valid_pool_vals.append(float(v))

            v_min = min(valid_pool_vals) if valid_pool_vals else None
            v_max = max(valid_pool_vals) if valid_pool_vals else None

            criteria_meta.append({
                "name": c_name,
                "metric": m_name,
                "mode": mode,
                "operator": crit.get("operator") or (">=" if mode == "threshold" else mode),
                "threshold_value": crit.get("threshold_value") if "threshold_value" in crit else crit.get("threshold"),
                "v_min": v_min,
                "v_max": v_max,
                "weight": norm_weights.get(c_name, 0.0)
            })

        # Step 2: Compute scores for each candidate
        candidate_records: List[Dict[str, Any]] = []

        for orig_idx, c in enumerate(candidates):
            if not isinstance(c, dict):
                continue

            raw_c_id = c.get(resolved_key)
            c_id = str(raw_c_id).strip() if (raw_c_id is not None and str(raw_c_id).strip() != "") else f"Candidate_{orig_idx + 1}"
            crit_contributions: Dict[str, float] = {}
            crit_scores: Dict[str, float] = {}
            crit_satisfied: List[str] = []
            crit_failed: List[str] = []
            total_score = 0.0

            for cm in criteria_meta:
                c_name = cm["name"]
                m_name = cm["metric"]
                mode = cm["mode"]
                w = cm["weight"]
                raw_val = c.get(m_name) if m_name else None

                norm_score = 0.0

                if mode == "maximize":
                    if raw_val is None or not _is_valid_finite_number(raw_val) or cm["v_min"] is None:
                        norm_score = 0.0
                        crit_failed.append(c_name)
                    else:
                        val = float(raw_val)
                        if cm["v_max"] == cm["v_min"]:
                            norm_score = 1.0
                        else:
                            norm_score = (val - cm["v_min"]) / (cm["v_max"] - cm["v_min"])
                        if norm_score == 1.0:
                            crit_satisfied.append(c_name)
                        else:
                            crit_failed.append(c_name)

                elif mode == "minimize":
                    if raw_val is None or not _is_valid_finite_number(raw_val) or cm["v_min"] is None:
                        norm_score = 0.0
                        crit_failed.append(c_name)
                    else:
                        val = float(raw_val)
                        if cm["v_max"] == cm["v_min"]:
                            norm_score = 1.0
                        else:
                            norm_score = (cm["v_max"] - val) / (cm["v_max"] - cm["v_min"])
                        if norm_score == 1.0:
                            crit_satisfied.append(c_name)
                        else:
                            crit_failed.append(c_name)

                else:  # threshold condition
                    th_val = cm["threshold_value"]
                    if raw_val is None or th_val is None:
                        norm_score = 0.0
                        crit_failed.append(c_name)
                    else:
                        crit_eval = self.evaluate_criterion(
                            criterion_name=c_name,
                            metric_name=m_name or "metric",
                            operator=cm["operator"],
                            threshold_value=th_val,
                            actual_value=raw_val
                        )
                        if crit_eval.is_met:
                            norm_score = 1.0
                            crit_satisfied.append(c_name)
                        else:
                            norm_score = 0.0
                            crit_failed.append(c_name)

                contribution = round(norm_score * w, 4)
                total_score += norm_score * w
                crit_contributions[c_name] = contribution
                crit_scores[c_name] = round(norm_score, 4)

            candidate_records.append({
                "candidate_id": c_id,
                resolved_key: c_id,
                "score": round(total_score, 4),
                "criterion_contributions": crit_contributions,
                "criteria_scores": crit_scores,
                "criteria_satisfied": crit_satisfied,
                "criteria_failed": crit_failed,
                "details": c,
                "_orig_idx": orig_idx
            })

        # Step 3: Deterministic tie-breaking sort:
        # 1. Total score descending (-score)
        # 2. Candidate identifier string ascending
        # 3. Original dataset row index ascending
        def sort_key(rec):
            return (-rec["score"], str(rec["candidate_id"]), rec["_orig_idx"])

        sorted_records = sorted(candidate_records, key=sort_key)

        rankings: List[Dict[str, Any]] = []
        limit = top_n if (top_n is not None and top_n > 0) else len(sorted_records)

        for rank_idx, rec in enumerate(sorted_records[:limit], start=1):
            cleaned = dict(rec)
            cleaned["rank"] = rank_idx
            cleaned.pop("_orig_idx", None)
            rankings.append(cleaned)

        return rankings

    def evaluate_multi_criteria(
        self,
        candidates: List[Dict[str, Any]],
        criteria: List[Dict[str, Any]],
        weights: Optional[Union[Dict[str, Any], List[Any]]] = None,
        key_col: Optional[str] = None,
        top_n: Optional[int] = None,
        evidence_items: Optional[List[EvidenceItem]] = None,
        question: Optional[str] = None,
        robustness: Optional[RobustnessCheck] = None
    ) -> DecisionAnalysis:
        """
        Executes a complete Multi-Criteria Decision Evaluation synthesizing criteria, rankings,
        and traceable recommendations into a DecisionAnalysis object.
        """
        anal_id = self.generate_id("anal")
        fact_ids = [ev.evidence_id for ev in (evidence_items or []) if ev.evidence_type == EvidenceType.FACT]
        rob_status = robustness.status if robustness else "INSUFFICIENT_EVIDENCE"

        # Edge case: Empty candidates
        if not candidates or not isinstance(candidates, list) or len(candidates) == 0:
            rec = self.build_recommendation(
                action_title="Gather candidate data",
                rationale="No candidate records were provided for multi-criteria decision evaluation.",
                supporting_evidence_ids=fact_ids,
                robustness_status="INSUFFICIENT_EVIDENCE",
                limitations=["Candidate dataset is empty."]
            )
            return DecisionAnalysis(
                analysis_id=anal_id,
                summary="Multi-criteria decision evaluation: candidate pool is empty.",
                criteria_evaluated=[],
                rankings=[],
                recommendation=rec,
                robustness=robustness
            )

        # Edge case: Empty criteria
        if not criteria or not isinstance(criteria, list) or len(criteria) == 0:
            rec = self.build_recommendation(
                action_title="Define decision criteria",
                rationale="No evaluation criteria were specified for decision evaluation.",
                supporting_evidence_ids=fact_ids,
                robustness_status="INSUFFICIENT_EVIDENCE",
                limitations=["Criteria list is empty."]
            )
            return DecisionAnalysis(
                analysis_id=anal_id,
                summary="Multi-criteria decision evaluation: no criteria specified.",
                criteria_evaluated=[],
                rankings=[],
                recommendation=rec,
                robustness=robustness
            )

        # Validate weights
        is_valid, err_msg, norm_weights = self.validate_weights(criteria, weights)
        if not is_valid:
            rec = self.build_recommendation(
                action_title="Review criterion weights",
                rationale=f"Multi-criteria evaluation aborted due to invalid weights: {err_msg}",
                supporting_evidence_ids=fact_ids,
                robustness_status="INSUFFICIENT_EVIDENCE",
                limitations=[err_msg or "Invalid weights."]
            )
            return DecisionAnalysis(
                analysis_id=anal_id,
                summary=f"Multi-criteria evaluation error: {err_msg}",
                criteria_evaluated=[],
                rankings=[],
                recommendation=rec,
                robustness=robustness
            )

        rankings = self.rank_candidates_multi_criteria(
            candidates=candidates,
            criteria=criteria,
            weights=weights,
            key_col=key_col,
            top_n=top_n
        )

        top_candidate = rankings[0] if rankings else None
        first_cand = candidates[0] if isinstance(candidates[0], dict) else {}
        resolved_key = key_col or next((c for c in ["candidate_id", "candidate", "name", "id", "region", "product_name", "customer_name", "category", "item"] if c in first_cand), list(first_cand.keys())[0] if first_cand else "candidate")

        # Build evaluated criteria list for top candidate
        criteria_evaluated: List[DecisionCriterion] = []
        for idx, crit in enumerate(criteria, start=1):
            c_name = crit.get("name") or crit.get("criterion_name") or f"criterion_{idx}"
            m_name = crit.get("metric") or crit.get("metric_name") or "metric"
            op = crit.get("operator") or crit.get("direction") or ">="
            th = crit.get("threshold_value") if "threshold_value" in crit else crit.get("threshold", "N/A")
            act_val = top_candidate["details"].get(m_name) if top_candidate else None

            crit_item = self.evaluate_criterion(
                criterion_name=c_name,
                metric_name=m_name,
                operator=str(op),
                threshold_value=th,
                actual_value=act_val
            )
            criteria_evaluated.append(crit_item)

        if top_candidate:
            top_id = top_candidate["candidate_id"]
            top_score = top_candidate["score"]
            action_title = f"Prioritize {resolved_key.capitalize()} '{top_id}'"
            rationale = (
                f"Candidate '{top_id}' achieved the highest weighted multi-criteria score ({top_score}) "
                f"across {len(criteria)} evaluated criteria ({', '.join(norm_weights.keys())})."
            )
            effective_status = robustness.status if robustness else "STABLE"
            rec = self.build_recommendation(
                action_title=action_title,
                rationale=rationale,
                supporting_evidence_ids=fact_ids,
                robustness_status=effective_status
            )
        else:
            rec = self.build_recommendation(
                action_title="Investigate candidates",
                rationale="Could not determine a leading candidate.",
                supporting_evidence_ids=fact_ids,
                robustness_status="INSUFFICIENT_EVIDENCE"
            )

        summary = (
            f"Multi-criteria decision analysis evaluated {len(criteria)} criteria across {len(candidates)} candidates. "
            f"Top candidate: '{top_candidate['candidate_id']}' with score {top_candidate['score']} "
            f"(robustness status: '{rec.robustness_status}')."
        ) if top_candidate else "Multi-criteria decision analysis produced no rankings."

        return DecisionAnalysis(
            analysis_id=anal_id,
            summary=summary,
            criteria_evaluated=criteria_evaluated,
            rankings=rankings,
            recommendation=rec,
            robustness=robustness
        )

    # Alias for convenience
    evaluate_multi_criteria_decision = evaluate_multi_criteria

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
        robustness: Optional[RobustnessCheck] = None,
        criteria: Optional[List[Dict[str, Any]]] = None,
        weights: Optional[Union[Dict[str, Any], List[Any]]] = None,
        key_col: Optional[str] = None
    ) -> DecisionAnalysis:
        """
        Main decision intelligence synthesis function.
        Generates criteria evaluations, rankings, and actionable recommendation from verified evidence.
        If explicit multi-criteria are provided, dispatches to evaluate_multi_criteria.
        Otherwise maintains 100% backward-compatible single-metric decision analysis.
        """
        if criteria is not None and len(criteria) > 0:
            return self.evaluate_multi_criteria(
                candidates=query_data or [],
                criteria=criteria,
                weights=weights,
                key_col=key_col,
                evidence_items=evidence_items,
                question=question,
                robustness=robustness
            )

        anal_id = self.generate_id("anal")
        criteria_list: List[DecisionCriterion] = []
        rankings: List[Dict[str, Any]] = []

        fact_ids = [ev.evidence_id for ev in evidence_items if ev.evidence_type == EvidenceType.FACT]
        rob_status = robustness.status if robustness else "INSUFFICIENT_EVIDENCE"

        if query_data and len(query_data) > 0:
            first_row = query_data[0]
            # Identify primary entity key and metric column
            eff_key = key_col or next((c for c in ["candidate_id", "candidate", "name", "id", "region", "product_name", "customer_name", "category"] if c in first_row), list(first_row.keys())[0])
            num_cols = [c for c, v in first_row.items() if isinstance(v, (int, float))]

            if num_cols:
                metric_col = num_cols[0]
                rankings = self.rank_candidates(query_data, key_col=eff_key, metric_col=metric_col, top_n=5)

                top_candidate = rankings[0] if rankings else None
                top_val = top_candidate.get(metric_col) if top_candidate else 0.0

                crit = self.evaluate_criterion(
                    criterion_name=f"Top {eff_key.capitalize()} Value Evaluation",
                    metric_name=metric_col,
                    operator=">",
                    threshold_value=0.0,
                    actual_value=top_val
                )
                criteria_list.append(crit)

                action_title = f"Prioritize {eff_key.capitalize()} '{top_candidate[eff_key]}'" if top_candidate else "Investigate top business segment"
                rationale = f"Observed top performance in '{top_candidate[eff_key]}' with {metric_col} = {top_val} based on verified database evidence." if top_candidate else "Database query returned metrics."

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

        summary = f"Decision analysis evaluated {len(criteria_list)} criteria and produced rankings for {len(rankings)} candidates with robustness status '{rob_status}'."

        return DecisionAnalysis(
            analysis_id=anal_id,
            summary=summary,
            criteria_evaluated=criteria_list,
            rankings=rankings,
            recommendation=rec,
            robustness=robustness
        )
