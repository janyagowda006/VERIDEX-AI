import os
import re
import json
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.schemas.ai import AskResponse
from app.ai.provider import BaseLLMProvider, MockLLMProvider
from app.ai.orchestrator import run_investigation_loop
from app.services.investigation_service import InvestigationService
from app.ai.eval.schemas import (
    BenchmarkItem,
    CaseEvaluation,
    BenchmarkReport,
    BenchmarkCategory
)

logger = logging.getLogger(__name__)


class ResponseEvaluator:
    """
    Evaluates a structured AskResponse object against a BenchmarkItem baseline using deterministic rules.
    """

    @staticmethod
    def extract_tables_from_sql(sql_str: str) -> List[str]:
        """
        Extracts database table names from a SQL query string using regex matching.
        """
        if not sql_str:
            return []
        known_tables = ["customers", "products", "orders", "order_items"]
        found = []
        sql_lower = sql_str.lower()
        for t in known_tables:
            if re.search(r'\b' + t + r'\b', sql_lower):
                found.append(t)
        return found

    @classmethod
    def evaluate_case(
        cls,
        item: BenchmarkItem,
        response: AskResponse,
        latency_ms: float,
        investigation_id: Optional[str] = None
    ) -> CaseEvaluation:
        """
        Evaluates a single AskResponse against ground-truth benchmark item parameters.
        """
        if not response or not response.success:
            return CaseEvaluation(
                item_id=item.id,
                category=item.category,
                question=item.question,
                success=False,
                execution_time_ms=latency_ms,
                turns_used=response.metadata.get("total_turns", 0) if (response and response.metadata) else 0,
                tool_calls_count=len(response.tool_calls) if (response and response.tool_calls) else 0,
                error_message=response.error if response else "Execution failed with empty response.",
                investigation_id=investigation_id
            )

        # 1. SQL Execution Evaluation
        tool_calls = response.tool_calls or []
        last_sql = None
        sql_success = False
        tables_found: List[str] = []

        if tool_calls:
            last_record = tool_calls[-1]
            sql_success = last_record.result.success if last_record.result else False
            raw_sql = last_record.arguments.get("sql", "") if isinstance(last_record.arguments, dict) else ""
            last_sql = str(raw_sql)
            tables_found = cls.extract_tables_from_sql(last_sql)
        elif item.category == BenchmarkCategory.INSUFFICIENT:
            # Out-of-scope/insufficient evidence queries correctly make 0 tool calls
            sql_success = True

        # 2. Groundedness & Citation Evaluation
        claims = response.claims or []
        evidence = response.evidence or []
        total_claims = len(claims)
        unsupported_claims = sum(1 for c in claims if not c.is_supported)

        groundedness_score = 1.0
        if total_claims > 0:
            supported_count = total_claims - unsupported_claims
            groundedness_score = round(supported_count / total_claims, 4)

        # Citation Precision & Recall
        valid_ev_ids = {ev.evidence_id for ev in evidence}
        all_cited_ids = []
        for c in claims:
            all_cited_ids.extend(c.evidence_ids)

        total_cited = len(all_cited_ids)
        valid_cited = sum(1 for eid in all_cited_ids if eid in valid_ev_ids)

        citation_precision = 1.0 if total_cited == 0 else round(valid_cited / total_cited, 4)
        total_available = len(valid_ev_ids)
        unique_valid_cited = len(set(all_cited_ids).intersection(valid_ev_ids))
        citation_recall = 1.0 if total_available == 0 else round(unique_valid_cited / total_available, 4)

        # 3. Decision & Robustness Agreement
        decision_agreement: Optional[bool] = None
        robustness_agreement: Optional[bool] = None

        if item.expected_decision_status:
            actual_status = None
            if response.analysis and response.analysis.robustness:
                actual_status = response.analysis.robustness.status
            elif response.metadata and "robustness_status" in response.metadata:
                actual_status = response.metadata["robustness_status"]

            if actual_status:
                decision_agreement = (actual_status.upper() == item.expected_decision_status.upper())
                robustness_agreement = (actual_status.upper() == item.expected_decision_status.upper())

        return CaseEvaluation(
            item_id=item.id,
            category=item.category,
            question=item.question,
            success=response.success,
            execution_time_ms=latency_ms,
            turns_used=response.metadata.get("total_turns", 1) if response.metadata else 1,
            tool_calls_count=len(tool_calls),
            sql_executed=last_sql,
            sql_success=sql_success,
            tables_accessed=tables_found,
            evidence_count=len(evidence),
            claims_count=total_claims,
            unsupported_claims_count=unsupported_claims,
            groundedness_score=groundedness_score,
            citation_precision=citation_precision,
            citation_recall=citation_recall,
            decision_agreement=decision_agreement,
            robustness_agreement=robustness_agreement,
            error_message=response.error,
            investigation_id=investigation_id
        )


class BenchmarkRunner:
    """
    Executes a benchmark dataset against the VERIDEX decision intelligence orchestration pipeline.
    """

    def __init__(self, dataset_path: Optional[str] = None):
        if dataset_path is None:
            dataset_path = os.path.join(os.path.dirname(__file__), "benchmark_dataset.json")
        self.dataset_path = dataset_path
        self.items: List[BenchmarkItem] = self._load_dataset()

    def _load_dataset(self) -> List[BenchmarkItem]:
        if not os.path.exists(self.dataset_path):
            raise FileNotFoundError(f"Benchmark dataset file not found: {self.dataset_path}")
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        return [BenchmarkItem(**item) for item in raw_data]

    def run_benchmark(
        self,
        db: Session,
        provider: BaseLLMProvider,
        max_turns: int = 3,
        provider_name: str = "mock",
        persist_investigations: bool = False
    ) -> BenchmarkReport:
        """
        Runs all benchmark dataset items sequentially and aggregates results into a BenchmarkReport.
        Optionally persists each benchmark investigation to the database via InvestigationService.
        """
        evaluations: List[CaseEvaluation] = []
        total_cases = len(self.items)

        for item in self.items:
            # Reset call count per benchmark item for stateful mock provider
            if hasattr(provider, "call_count"):
                provider.call_count = 0

            inv_id: Optional[str] = None
            if persist_investigations and db:
                try:
                    inv = InvestigationService.create_investigation(
                        db=db,
                        question=item.question
                    )
                    inv_id = inv.investigation_id
                except Exception as db_err:
                    logger.warning(f"Failed to create benchmark investigation record for item {item.id}: {db_err}")

            start_time = time.perf_counter()
            response = None
            try:
                response = run_investigation_loop(
                    question=item.question,
                    db=db,
                    provider=provider,
                    max_turns=max_turns
                )
            except Exception as exc:
                end_time = time.perf_counter()
                latency_ms = round((end_time - start_time) * 1000.0, 2)
                if persist_investigations and db and inv_id:
                    try:
                        InvestigationService.update_investigation_failure(
                            db=db,
                            investigation_id=inv_id,
                            error_message=str(exc),
                            execution_time_ms=latency_ms
                        )
                    except Exception as db_err:
                        logger.warning(f"Failed to persist failed benchmark investigation {inv_id}: {db_err}")

                err_response = AskResponse(
                    success=False,
                    question=item.question,
                    answer="",
                    error=str(exc)
                )
                case_eval = ResponseEvaluator.evaluate_case(
                    item=item,
                    response=err_response,
                    latency_ms=latency_ms,
                    investigation_id=inv_id
                )
                evaluations.append(case_eval)
                continue

            end_time = time.perf_counter()
            latency_ms = round((end_time - start_time) * 1000.0, 2)

            if persist_investigations and db and inv_id:
                try:
                    if response and response.success:
                        InvestigationService.update_investigation_success(
                            db=db,
                            investigation_id=inv_id,
                            response=response,
                            execution_time_ms=latency_ms
                        )
                        if response.metadata is not None:
                            response.metadata["investigation_id"] = inv_id
                    else:
                        err_msg = response.error if response else "Execution failed with empty response"
                        InvestigationService.update_investigation_failure(
                            db=db,
                            investigation_id=inv_id,
                            error_message=err_msg or "Execution failed",
                            execution_time_ms=latency_ms
                        )
                except Exception as db_err:
                    logger.warning(f"Failed to persist benchmark investigation {inv_id}: {db_err}")

            case_eval = ResponseEvaluator.evaluate_case(
                item=item,
                response=response,
                latency_ms=latency_ms,
                investigation_id=inv_id
            )
            evaluations.append(case_eval)

        # Aggregate summary metrics
        successful_cases = sum(1 for e in evaluations if e.success)
        failed_cases = total_cases - successful_cases

        sql_success_count = sum(1 for e in evaluations if e.sql_success)
        sql_exec_rate = round(sql_success_count / total_cases, 4)

        groundedness_rate = round(sum(e.groundedness_score for e in evaluations) / total_cases, 4)
        prec_rate = round(sum(e.citation_precision for e in evaluations) / total_cases, 4)
        rec_rate = round(sum(e.citation_recall for e in evaluations) / total_cases, 4)

        total_claims_all = sum(e.claims_count for e in evaluations)
        total_unsupported_all = sum(e.unsupported_claims_count for e in evaluations)
        unsupported_rate = 0.0 if total_claims_all == 0 else round(total_unsupported_all / total_claims_all, 4)

        decision_evals = [e.decision_agreement for e in evaluations if e.decision_agreement is not None]
        decision_agree_rate = 1.0 if not decision_evals else round(sum(1 for d in decision_evals if d) / len(decision_evals), 4)

        robust_evals = [e.robustness_agreement for e in evaluations if e.robustness_agreement is not None]
        robust_agree_rate = 1.0 if not robust_evals else round(sum(1 for r in robust_evals if r) / len(robust_evals), 4)

        avg_lat = round(sum(e.execution_time_ms for e in evaluations) / total_cases, 2)

        return BenchmarkReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            benchmark_version="1.0.0",
            provider_name=provider_name,
            total_cases=total_cases,
            successful_cases=successful_cases,
            failed_cases=failed_cases,
            sql_execution_success_rate=sql_exec_rate,
            groundedness_rate=groundedness_rate,
            citation_precision=prec_rate,
            citation_recall=rec_rate,
            unsupported_claim_rate=unsupported_rate,
            decision_agreement_rate=decision_agree_rate,
            robustness_agreement_rate=robust_agree_rate,
            average_latency_ms=avg_lat,
            case_evaluations=evaluations
        )
