import json
import re
import math
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.schemas.ai import AskResponse, ToolCallRecord
from app.schemas.evidence import EvidenceItem, ClaimEvidence, EvidenceType
from app.schemas.decision import DecisionAnalysis, RobustnessCheck
from app.schemas.sql_tool import SQLQueryRequest, SQLQueryResult
from app.services.schema_introspection import get_database_schema
from app.services.evidence_assembler import EvidenceAssembler
from app.services.evidence_calculations import EvidenceCalculator
from app.services.decision_engine import DecisionEngine
from app.services.robustness import RobustnessEngine
from app.tools.sql_tool import execute_read_only_sql
from app.tools.registry import ToolRegistry, ToolExecutionResult
from app.services.claim_checker import verify_answer
from app.schemas.decomposition import DecompositionResponse
from app.schemas.campaign_impact import CampaignImpactResponse
from app.ai.prompts import (
    SYSTEM_PROMPT_V3,
    format_schema_for_prompt,
    format_deterministic_reasoning_context
)
from app.ai.provider import BaseLLMProvider

logger = logging.getLogger(__name__)

DEFAULT_SCENARIO_SHIFT_PCT: float = 10.0


def _normalize_sql(sql_str: str) -> str:
    """
    Normalizes a SQL string by stripping whitespace, collapsing internal spaces, and converting to uppercase.
    Used for duplicate query detection.
    """
    if not sql_str:
        return ""
    return " ".join(sql_str.strip().split()).upper()


def _clean_text_tags(text: str) -> str:
    """
    Strips raw evidence tags like [ev_fact_1] or malformed bracket tags [ev_...] from text.
    """
    if not text:
        return ""
    cleaned = re.sub(r'\[ev_[^\]]*\]', '', text)
    cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\s+\.', '.', cleaned)
    cleaned = re.sub(r'\s+,', ',', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _split_into_sentences(text: str) -> List[str]:
    """
    Splits text into sentence units while preserving decimal points in numbers (e.g. $1.2M, 18.4%)
    and keeping trailing/attached evidence tags with each sentence.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    units = []
    pattern = re.compile(r'((?:(?![\.!\?](?:\s|\[|$)).|\d\.\d)+[\.!\?]?(?:\s*\[[^\]]+\])*)')
    for line in lines:
        matches = [m.group(0).strip() for m in pattern.finditer(line) if m.group(0).strip()]
        if matches:
            units.extend(matches)
        else:
            units.append(line)
    return units


def _is_valid_finite_number(val: Any) -> bool:
    """Validates that a value is a valid, finite real number (not None, bool, str, NaN, or inf)."""
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float)):
        return False
    try:
        return math.isfinite(float(val))
    except (ValueError, TypeError, OverflowError):
        return False


def _evaluate_orchestrated_robustness(
    robustness_engine: RobustnessEngine,
    evidence_items: List[EvidenceItem],
    query_data: Optional[List[Dict[str, Any]]] = None,
    scenario_shift_pct: float = DEFAULT_SCENARIO_SHIFT_PCT
) -> RobustnessCheck:
    """
    Evaluates robustness deterministically across automated multi-scenario stress tests (+/- scenario_shift_pct)
    when query data contains valid numeric candidate metrics.
    Falls back to baseline single-scenario assessment if query data is non-numeric or empty.
    Never mutates original query_data.
    """
    shift_val = float(scenario_shift_pct) if _is_valid_finite_number(scenario_shift_pct) and float(scenario_shift_pct) > 0.0 else DEFAULT_SCENARIO_SHIFT_PCT

    if not isinstance(query_data, list) or len(query_data) == 0 or not isinstance(query_data[0], dict) or not query_data[0]:
        return robustness_engine.run_robustness_assessment(
            evidence_items=evidence_items,
            query_data=query_data
        )

    first_row = query_data[0]

    # Identify primary candidate key column
    key_col = next(
        (c for c in ["candidate_id", "candidate", "name", "id", "region", "product_name", "customer_name", "category"] if c in first_row),
        list(first_row.keys())[0]
    )

    # Identify primary numeric metric column
    non_key_cols = [c for c in first_row.keys() if c != key_col]
    metric_col: Optional[str] = None
    for c in non_key_cols:
        if any(_is_valid_finite_number(r.get(c)) for r in query_data if isinstance(r, dict)):
            metric_col = c
            break

    if not metric_col:
        return robustness_engine.run_robustness_assessment(
            evidence_items=evidence_items,
            query_data=query_data
        )

    # Build deterministic scenario datasets without mutating baseline query_data
    minus_rows: List[Dict[str, Any]] = []
    plus_rows: List[Dict[str, Any]] = []

    for row in query_data:
        r_minus = dict(row)
        r_plus = dict(row)
        if metric_col in row and _is_valid_finite_number(row[metric_col]):
            val = float(row[metric_col])
            r_minus[metric_col] = round(val * (1.0 - shift_val / 100.0), 4)
            r_plus[metric_col] = round(val * (1.0 + shift_val / 100.0), 4)
        minus_rows.append(r_minus)
        plus_rows.append(r_plus)

    shift_int = int(shift_val) if shift_val.is_integer() else shift_val

    scenarios = [
        {
            "scenario_name": f"{metric_col}_minus_{shift_int}_percent",
            "assumptions": {"metric": metric_col, "shift_pct": -shift_val},
            "data": minus_rows
        },
        {
            "scenario_name": f"{metric_col}_plus_{shift_int}_percent",
            "assumptions": {"metric": metric_col, "shift_pct": shift_val},
            "data": plus_rows
        }
    ]

    return robustness_engine.evaluate_multi_scenario_robustness(
        baseline_data=query_data,
        scenarios=scenarios,
        evidence_items=evidence_items,
        key_col=key_col,
        metric_col=metric_col,
        threshold_pct=5.0,
        scenario_description=f"Automated multi-scenario metric shift evaluation (+/-{shift_val}%)"
    )


def _build_claims_and_evidence(
    answer: str,
    evidence_items: List[EvidenceItem]
) -> tuple[List[ClaimEvidence], List[EvidenceItem]]:
    """
    Builds claim-evidence mapping and categorizes claims into FACT, DERIVED_FACT, and INFERENCE.
    Parses evidence citation tags (e.g. [ev_fact_1], [ev_derived_1]) from answer text, validates them against
    known evidence items, and creates structured ClaimEvidence mappings.
    Enforces evidence consistency: unknown or invented evidence IDs are rejected and unsupported claims marked is_supported=False.
    """
    final_evidence = list(evidence_items)
    valid_evidence_map = {ev.evidence_id: ev for ev in final_evidence}

    # Check if answer contains any explicit evidence tags matching [ev_...]
    has_explicit_tags = bool(re.search(r'\[ev_[a-zA-Z0-9_]+\]', answer))

    claims: List[ClaimEvidence] = []
    claim_idx = 0

    if has_explicit_tags:
        # Match sentence units along with any trailing/attached evidence tags
        raw_units = _split_into_sentences(answer)

        for unit in raw_units:
            # Find candidate evidence tags in unit
            tag_matches = re.findall(r'\[(ev_[a-zA-Z0-9_]+)\]', unit)

            # Clean raw tags from claim text
            clean_claim = _clean_text_tags(unit)
            if not clean_claim:
                continue

            # Validate extracted tags against known evidence items (uniquified, order preserved)
            valid_ids: List[str] = []
            for tid in tag_matches:
                if tid in valid_evidence_map and tid not in valid_ids:
                    valid_ids.append(tid)

            is_supported = len(valid_ids) > 0

            # Determine claim evidence type based on referenced evidence items
            if valid_ids:
                ref_types = {valid_evidence_map[tid].evidence_type for tid in valid_ids}
                if EvidenceType.INFERENCE in ref_types:
                    claim_type = EvidenceType.INFERENCE
                elif EvidenceType.DERIVED_FACT in ref_types:
                    claim_type = EvidenceType.DERIVED_FACT
                else:
                    claim_type = EvidenceType.FACT
            else:
                # Unsupported claim: check for qualitative inference indicators
                inference_keywords = ["may indicate", "suggests", "likely", "associated with", "inference", "trend", "potential", "recommend", "assume"]
                if any(kw in clean_claim.lower() for kw in inference_keywords):
                    claim_type = EvidenceType.INFERENCE
                else:
                    claim_type = EvidenceType.FACT

            claim_idx += 1
            claims.append(ClaimEvidence(
                claim_id=f"claim_{claim_idx}",
                claim_text=clean_claim,
                evidence_ids=valid_ids,
                evidence_type=claim_type,
                is_supported=is_supported
            ))

    else:
        # Fallback for answers without explicit tags (legacy/mock text)
        fact_ids = [ev.evidence_id for ev in final_evidence if ev.evidence_type == EvidenceType.FACT]
        derived_ids = [ev.evidence_id for ev in final_evidence if ev.evidence_type == EvidenceType.DERIVED_FACT]

        if fact_ids:
            claim_idx += 1
            claims.append(ClaimEvidence(
                claim_id=f"claim_{claim_idx}",
                claim_text="Database query execution returned observed factual business metrics.",
                evidence_ids=fact_ids,
                evidence_type=EvidenceType.FACT,
                is_supported=True
            ))

        if derived_ids:
            claim_idx += 1
            claims.append(ClaimEvidence(
                claim_id=f"claim_{claim_idx}",
                claim_text="Deterministic arithmetic calculation derived from database facts.",
                evidence_ids=derived_ids,
                evidence_type=EvidenceType.DERIVED_FACT,
                is_supported=True
            ))

        inference_keywords = ["may indicate", "suggests", "likely", "associated with", "inference", "trend", "potential"]
        if any(kw in answer.lower() for kw in inference_keywords):
            claim_idx += 1
            inf_id = f"ev_inf_{claim_idx}"
            inf_item = EvidenceItem(
                evidence_id=inf_id,
                evidence_type=EvidenceType.INFERENCE,
                description="Qualitative interpretation derived from database evidence.",
                source=None,
                calculation=None,
                limitations=["Qualitative interpretation generated by AI engine; requires business domain validation."]
            )
            final_evidence.append(inf_item)

            claims.append(ClaimEvidence(
                claim_id=f"claim_{claim_idx}",
                claim_text=f"Qualitative analysis of observed findings: {answer[:120]}...",
                evidence_ids=[inf_id],
                evidence_type=EvidenceType.INFERENCE,
                is_supported=True
            ))

    return claims, final_evidence


def _format_prior_turns_context(prior_turns: List[Any]) -> str:
    """
    Formats bounded prior conversation turns into structured prompt context.
    Strictly instructs the model that prior context is historical reference only, not fresh FACT evidence.
    """
    if not prior_turns:
        return ""

    context_lines = [
        "<PRIOR_CONVERSATION_CONTEXT>",
        "CRITICAL INSTRUCTION: The following conversation history provides context for the current follow-up question.",
        "Prior assistant statements are historical context ONLY and MUST NOT be treated as fresh FACT evidence.",
        "Current turn FACT evidence MUST be derived exclusively from SQL tool calls executed in the current turn.",
        ""
    ]

    for turn in prior_turns:
        t_num = getattr(turn, "turn_number", 1)
        u_q = getattr(turn, "user_question", "")
        res_json_raw = getattr(turn, "result_json", None)
        ans_text = ""
        if res_json_raw:
            try:
                payload = json.loads(res_json_raw) if isinstance(res_json_raw, str) else res_json_raw
                ans_text = payload.get("answer", "")
            except Exception:
                pass

        context_lines.append(f"Turn {t_num}:")
        context_lines.append(f"User Question: {u_q}")
        if ans_text:
            context_lines.append(f"Assistant Answer: {ans_text}")
        context_lines.append("")

    context_lines.append("</PRIOR_CONVERSATION_CONTEXT>")
    return "\n".join(context_lines)


def run_investigation_loop(
    question: str,
    db: Session,
    provider: BaseLLMProvider,
    max_turns: int = 3,
    prior_turns: Optional[List[Any]] = None
) -> AskResponse:
    """
    Custom bounded decision intelligence orchestration loop with Evidence Assembly, Decision Engine, and Robustness Testing.
    Orchestrates typed specialized tools from ToolRegistry (sql_query, driver_decomposition, campaign_impact, claim_verification).
    Supports multi-step reasoning turns and bounded prior conversation context.
    """
    if db is None:
        return AskResponse(
            success=False,
            question=question,
            answer="",
            claims=[],
            evidence=[],
            analysis=None,
            tool_calls=[],
            error="Database session is required."
        )

    bounded_turns = min(max(max_turns, 1), 5)
    schema_context = get_database_schema(db)
    schema_text = format_schema_for_prompt(schema_context)

    # Initialize Typed Tool Registry
    registry = ToolRegistry()
    tool_definitions = registry.get_tool_definitions()

    prior_context_block = _format_prior_turns_context(prior_turns) if prior_turns else ""
    if prior_context_block:
        full_user_content = f"{prior_context_block}\n\nCURRENT QUESTION:\n{question}"
    else:
        full_user_content = question

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": full_user_content}
    ]

    tool_call_records: List[ToolCallRecord] = []
    assembler = EvidenceAssembler()
    calculator = EvidenceCalculator()
    decision_engine = DecisionEngine()
    robustness_engine = RobustnessEngine()

    evidence_items: List[EvidenceItem] = []
    last_query_data: Optional[List[Dict[str, Any]]] = None
    executed_queries: set[str] = set()

    for turn in range(1, bounded_turns + 1):
        response = provider.generate_turn(
            messages=messages,
            tools=tool_definitions,
            schema_text=schema_text
        )

        if response.error:
            return AskResponse(
                success=False,
                question=question,
                answer="",
                claims=[],
                evidence=evidence_items,
                analysis=None,
                tool_calls=tool_call_records,
                error=response.error
            )

        if response.has_tool_call and response.tool_call:
            tool_req = response.tool_call
            tool_name = tool_req.tool_name
            raw_args = tool_req.arguments if isinstance(tool_req.arguments, dict) else {}

            # Check for duplicate SQL queries when tool_name is sql_query
            if tool_name == "sql_query":
                sql_val = raw_args.get("sql")
                if isinstance(sql_val, str) and sql_val.strip():
                    norm_sql = _normalize_sql(sql_val.strip())
                    if norm_sql in executed_queries:
                        exec_res = ToolExecutionResult(
                            success=False,
                            tool_name="sql_query",
                            error_type="DUPLICATE_QUERY",
                            error_message="Duplicate SQL query detected; query was already executed in a previous turn."
                        )
                    else:
                        executed_queries.add(norm_sql)
                        exec_res = registry.execute_tool(
                            tool_name=tool_name,
                            db=db,
                            arguments=raw_args,
                            context_evidence=evidence_items
                        )
                else:
                    exec_res = registry.execute_tool(
                        tool_name=tool_name,
                        db=db,
                        arguments=raw_args,
                        context_evidence=evidence_items
                    )
            else:
                exec_res = registry.execute_tool(
                    tool_name=tool_name,
                    db=db,
                    arguments=raw_args,
                    context_evidence=evidence_items
                )

            # Build SQLQueryResult representation for ToolCallRecord
            if isinstance(exec_res.raw_response, SQLQueryResult):
                sql_result = exec_res.raw_response
            else:
                sql_result = SQLQueryResult(
                    success=exec_res.success,
                    sql=f"[{tool_name}] {json.dumps(raw_args)}",
                    data=[exec_res.output_data] if exec_res.output_data else [],
                    row_count=len(exec_res.evidence_items),
                    error_type=exec_res.error_type,
                    error_message=exec_res.error_message
                )

            record = ToolCallRecord(
                turn=turn,
                tool_name=tool_name,
                arguments=raw_args,
                result=sql_result
            )
            tool_call_records.append(record)

            # Aggregate evidence items produced by tool
            if exec_res.evidence_items:
                for ev in exec_res.evidence_items:
                    if not any(existing.evidence_id == ev.evidence_id for existing in evidence_items):
                        evidence_items.append(ev)

            # Extract structured query data for Decision and Robustness engine
            if exec_res.success:
                if tool_name == "sql_query" and sql_result.data:
                    last_query_data = sql_result.data
                elif tool_name == "driver_decomposition" and isinstance(exec_res.raw_response, DecompositionResponse):
                    d_resp = exec_res.raw_response
                    prim_breakdown = d_resp.breakdowns.get(d_resp.primary_dimension)
                    if prim_breakdown and prim_breakdown.drivers:
                        last_query_data = [
                            {
                                "candidate_id": dr.label,
                                "metric": dr.delta_amount,
                                "revenue_a": dr.revenue_a,
                                "revenue_b": dr.revenue_b
                            }
                            for dr in prim_breakdown.drivers
                        ]
                elif tool_name == "campaign_impact" and isinstance(exec_res.raw_response, CampaignImpactResponse):
                    c_resp = exec_res.raw_response
                    last_query_data = [
                        {"candidate_id": f"Exposed ({c_resp.target_region})", "metric": c_resp.exposed_change},
                        {"candidate_id": f"Control ({c_resp.target_region})", "metric": c_resp.control_change}
                    ]

            # Build tool result text for conversation turn
            avail_ids = [ev.evidence_id for ev in evidence_items]
            tool_res_text = json.dumps({
                "success": exec_res.success,
                "tool_name": tool_name,
                "output": exec_res.output_data,
                "available_evidence_ids": avail_ids,
                "error_type": exec_res.error_type,
                "error_message": exec_res.error_message
            }, default=str)

            display_args = json.dumps(raw_args)
            messages.append({"role": "model", "content": f"Requested tool '{tool_name}' with arguments: {display_args}"})
            messages.append({"role": "tool_result", "content": f"Tool Result for turn {turn}: {tool_res_text}"})

            # Inject reasoning context if query data is available
            if exec_res.success and last_query_data:
                inter_rob = _evaluate_orchestrated_robustness(
                    robustness_engine, evidence_items, last_query_data
                )
                inter_analysis = decision_engine.analyze_decision(
                    question=question,
                    evidence_items=evidence_items,
                    query_data=last_query_data,
                    robustness=inter_rob
                )
                reasoning_ctx = format_deterministic_reasoning_context(inter_analysis)
                if reasoning_ctx:
                    messages.append({"role": "user", "content": reasoning_ctx})

        elif response.content:
            # Model synthesized final answer
            claims, final_evidence = _build_claims_and_evidence(response.content, evidence_items)
            clean_answer = _clean_text_tags(response.content) if response.content else ""

            # Deterministic Claim Checker Integration
            try:
                verify_res = verify_answer(llm_text=response.content, evidence_list=final_evidence, tolerance=0.05)
                if verify_res and verify_res.total_claims > 0:
                    verified_sentences = {vc.sentence for vc in verify_res.verified}
                    unverified_sentences = {vc.sentence for vc in verify_res.unverified}
                    for cl in claims:
                        if cl.claim_text in verified_sentences or any(vc.sentence in cl.claim_text for vc in verify_res.verified):
                            cl.is_supported = True
                            for vc in verify_res.verified:
                                if vc.sentence in cl.claim_text or cl.claim_text in vc.sentence:
                                    for m_id in vc.matching_evidence_ids:
                                        if m_id not in cl.evidence_ids:
                                            cl.evidence_ids.append(m_id)
                        elif cl.claim_text in unverified_sentences and not cl.evidence_ids:
                            cl.is_supported = False
            except Exception as v_err:
                logger.warning("Claim verification integration error: %s", v_err)

            # Deterministic Robustness and Decision Analysis
            robustness_check = _evaluate_orchestrated_robustness(
                robustness_engine=robustness_engine,
                evidence_items=final_evidence,
                query_data=last_query_data
            )
            decision_analysis = decision_engine.analyze_decision(
                question=question,
                evidence_items=final_evidence,
                query_data=last_query_data,
                robustness=robustness_check
            )

            return AskResponse(
                success=True,
                question=question,
                answer=clean_answer,
                claims=claims,
                evidence=final_evidence,
                analysis=decision_analysis,
                tool_calls=tool_call_records,
                metadata={
                    "total_turns": turn,
                    "max_turns": bounded_turns,
                    "total_tool_calls": len(tool_call_records),
                    "total_evidence_items": len(final_evidence),
                    "total_claims": len(claims),
                    "robustness_status": robustness_check.status
                }
            )

    # Max turns reached without explicit content finish
    final_summary = f"Investigation reached the maximum allowed turn boundary ({bounded_turns} turns)."
    if tool_call_records:
        last_rec = tool_call_records[-1]
        if last_rec.result.success:
            final_summary += f" Executed {len(tool_call_records)} tool query(ies)."
        else:
            final_summary += f" Last tool call failed: {last_rec.result.error_message}"

    claims, final_evidence = _build_claims_and_evidence(final_summary, evidence_items)

    # Deterministic Claim Checker Integration for turn boundary summary
    try:
        verify_res = verify_answer(llm_text=final_summary, evidence_list=final_evidence, tolerance=0.05)
        if verify_res and verify_res.total_claims > 0:
            verified_sentences = {vc.sentence for vc in verify_res.verified}
            unverified_sentences = {vc.sentence for vc in verify_res.unverified}
            for cl in claims:
                if cl.claim_text in verified_sentences or any(vc.sentence in cl.claim_text for vc in verify_res.verified):
                    cl.is_supported = True
                elif cl.claim_text in unverified_sentences or any(vc.sentence in cl.claim_text for vc in verify_res.unverified):
                    cl.is_supported = False
    except Exception as v_err:
        logger.warning("Claim verification integration error: %s", v_err)

    robustness_check = _evaluate_orchestrated_robustness(
        robustness_engine=robustness_engine,
        evidence_items=final_evidence,
        query_data=last_query_data
    )
    decision_analysis = decision_engine.analyze_decision(
        question=question,
        evidence_items=final_evidence,
        query_data=last_query_data,
        robustness=robustness_check
    )

    return AskResponse(
        success=True,
        question=question,
        answer=final_summary,
        claims=claims,
        evidence=final_evidence,
        analysis=decision_analysis,
        tool_calls=tool_call_records,
        metadata={
            "total_turns": bounded_turns,
            "max_turns": bounded_turns,
            "total_tool_calls": len(tool_call_records),
            "total_evidence_items": len(final_evidence),
            "total_claims": len(claims),
            "robustness_status": robustness_check.status,
            "boundary_reached": True
        }
    )
