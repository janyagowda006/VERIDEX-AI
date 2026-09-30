import json
import re
import math
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
from app.ai.prompts import (
    SYSTEM_PROMPT_V3,
    format_schema_for_prompt,
    format_deterministic_reasoning_context
)
from app.ai.provider import BaseLLMProvider

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
    query_data: Optional[List[Dict[str, Any]]] = None
) -> RobustnessCheck:
    """
    Evaluates robustness deterministically across automated multi-scenario stress tests (+/-10% metric shifts)
    when query data contains valid numeric candidate metrics.
    Falls back to baseline single-scenario assessment if query data is non-numeric or empty.
    Never mutates original query_data.
    """
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
    minus_10_rows: List[Dict[str, Any]] = []
    plus_10_rows: List[Dict[str, Any]] = []

    for row in query_data:
        r_minus = dict(row)
        r_plus = dict(row)
        if metric_col in row and _is_valid_finite_number(row[metric_col]):
            val = float(row[metric_col])
            r_minus[metric_col] = round(val * (1.0 - DEFAULT_SCENARIO_SHIFT_PCT / 100.0), 4)
            r_plus[metric_col] = round(val * (1.0 + DEFAULT_SCENARIO_SHIFT_PCT / 100.0), 4)
        minus_10_rows.append(r_minus)
        plus_10_rows.append(r_plus)

    scenarios = [
        {
            "scenario_name": f"{metric_col}_minus_{int(DEFAULT_SCENARIO_SHIFT_PCT)}_percent",
            "assumptions": {"metric": metric_col, "shift_pct": -DEFAULT_SCENARIO_SHIFT_PCT},
            "data": minus_10_rows
        },
        {
            "scenario_name": f"{metric_col}_plus_{int(DEFAULT_SCENARIO_SHIFT_PCT)}_percent",
            "assumptions": {"metric": metric_col, "shift_pct": DEFAULT_SCENARIO_SHIFT_PCT},
            "data": plus_10_rows
        }
    ]

    return robustness_engine.evaluate_multi_scenario_robustness(
        baseline_data=query_data,
        scenarios=scenarios,
        evidence_items=evidence_items,
        key_col=key_col,
        metric_col=metric_col,
        threshold_pct=5.0,
        scenario_description="Automated multi-scenario metric shift evaluation"
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


def run_investigation_loop(
    question: str,
    db: Session,
    provider: BaseLLMProvider,
    max_turns: int = 3
) -> AskResponse:
    """
    Custom bounded decision intelligence orchestration loop with Evidence Assembly, Decision Engine, and Robustness Testing.
    Connects LLM reasoning to the safe read-only SQL tool and constructs deterministic decision intelligence payloads.
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

    tool_definitions = [{
        "name": "sql_query",
        "description": "Executes a safe read-only SQL SELECT query against the business database.",
        "parameters": {
            "sql": "string (SQL SELECT statement)",
            "max_rows": "integer (optional, default 100)"
        }
    }]

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": question}
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

            if tool_req.tool_name != "sql_query":
                err_msg = f"Unsupported tool requested by model: '{tool_req.tool_name}'"
                return AskResponse(
                    success=False,
                    question=question,
                    answer="",
                    claims=[],
                    evidence=evidence_items,
                    analysis=None,
                    tool_calls=tool_call_records,
                    error=err_msg
                )

            # Extract arguments and validate for malformed inputs or duplicate calls
            raw_args = tool_req.arguments if isinstance(tool_req.arguments, dict) else {}
            sql_val = raw_args.get("sql")
            max_r = raw_args.get("max_rows", 100) if isinstance(raw_args, dict) else 100

            if not isinstance(sql_val, str) or not sql_val.strip():
                sql_result = SQLQueryResult(
                    success=False,
                    sql=str(sql_val) if sql_val is not None else "",
                    error_type="MALFORMED_ARGUMENT",
                    error_message="Invalid tool argument: 'sql' must be a non-empty string."
                )
            else:
                sql_str = sql_val.strip()
                norm_sql = _normalize_sql(sql_str)

                if norm_sql in executed_queries:
                    sql_result = SQLQueryResult(
                        success=False,
                        sql=sql_str,
                        error_type="DUPLICATE_QUERY",
                        error_message="Duplicate SQL query detected; query was already executed in a previous turn."
                    )
                else:
                    executed_queries.add(norm_sql)
                    sql_req = SQLQueryRequest(sql=sql_str, max_rows=max_r)
                    sql_result = execute_read_only_sql(db, sql_req)

            record = ToolCallRecord(
                turn=turn,
                tool_name="sql_query",
                arguments=raw_args,
                result=sql_result
            )
            tool_call_records.append(record)

            if sql_result.success and sql_result.data:
                last_query_data = sql_result.data

            # Assemble FACT Evidence Item (only if query succeeded)
            if sql_result.success:
                fact_item = assembler.extract_fact_evidence(
                    sql_result,
                    description=f"Turn {turn} SQL query execution output."
                )
                if fact_item:
                    evidence_items.append(fact_item)

                    # If result has >= 2 numeric rows, compute derived comparison facts
                    if sql_result.data and len(sql_result.data) >= 2:
                        first_row = sql_result.data[0]
                        second_row = sql_result.data[1]
                        num_cols = [col for col, val in first_row.items() if isinstance(val, (int, float))]
                        if num_cols:
                            col_name = num_cols[0]
                            v1 = float(first_row[col_name])
                            v2 = float(second_row[col_name])
                            label1 = str(first_row.get("region") or first_row.get("product_name") or f"Row 1 ({col_name})")
                            label2 = str(second_row.get("region") or second_row.get("product_name") or f"Row 2 ({col_name})")

                            derived_item = calculator.percentage_change(
                                val_a=v1,
                                val_b=v2,
                                label_a=label1,
                                label_b=label2,
                                input_evidence_ids=[fact_item.evidence_id]
                            )
                            evidence_items.append(derived_item)

            # Append tool result to messages history for model's next turn
            avail_ids = [ev.evidence_id for ev in evidence_items]
            tool_res_text = json.dumps({
                "success": sql_result.success,
                "row_count": sql_result.row_count,
                "columns": sql_result.columns,
                "data": sql_result.data,
                "available_evidence_ids": avail_ids,
                "error_type": sql_result.error_type,
                "error_message": sql_result.error_message
            }, default=str)

            display_sql = raw_args.get("sql", "") if isinstance(raw_args, dict) else str(raw_args)
            messages.append({"role": "model", "content": f"Requested tool 'sql_query' with SQL: {display_sql}"})
            messages.append({"role": "tool_result", "content": f"Tool Result for turn {turn}: {tool_res_text}"})

            # Inject deterministic decision and multi-scenario robustness context for model's next turn
            if sql_result.success and last_query_data:
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

            # Run deterministic robustness assessment & decision engine
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
            final_summary += f" Executed {len(tool_call_records)} tool query(ies). Last query returned {last_rec.result.row_count} records."
        else:
            final_summary += f" Last tool call failed: {last_rec.result.error_message}"

    claims, final_evidence = _build_claims_and_evidence(final_summary, evidence_items)
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
