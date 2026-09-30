import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.db import get_db
from app.models.business_data import Customer, Product, Order, OrderItem
from app.services.metrics import calculate_net_revenue
from app.services.schema_introspection import get_database_schema
from app.tools.sql_tool import execute_read_only_sql
from app.schemas.sql_tool import SQLQueryRequest, SQLQueryResult, SchemaContext
from app.schemas.ai import AskRequest, AskResponse
from app.schemas.investigation import (
    InvestigationSummary,
    InvestigationDetail,
    InvestigationReassessRequest,
    InvestigationReassessResponse,
    InvestigationReviewCreate,
    InvestigationReviewResponse,
    InvestigationMetricsSummary,
    InvestigationTurnResponse
)
from app.services.investigation_service import InvestigationService
from app.ai.provider import BaseLLMProvider, get_llm_provider
from app.ai.orchestrator import run_investigation_loop

router = APIRouter()


@router.get("/health")
def health_check():
    """
    Health check endpoint to verify backend foundation startup.
    Returns HTTP 200 with status ok.
    """
    return {"status": "ok"}


@router.get("/db-status")
def db_status_check(db: Session = Depends(get_db)):
    """
    Development debug endpoint to verify database connectivity and table counts.
    """
    try:
        cust_count = db.query(func.count(Customer.customer_id)).scalar() or 0
        prod_count = db.query(func.count(Product.product_id)).scalar() or 0
        order_count = db.query(func.count(Order.order_id)).scalar() or 0
        item_count = db.query(func.count(OrderItem.order_item_id)).scalar() or 0
        net_revenue = calculate_net_revenue(db)

        return {
            "database_connected": True,
            "table_counts": {
                "customers": cust_count,
                "products": prod_count,
                "orders": order_count,
                "order_items": item_count
            },
            "summary_metrics": {
                "net_revenue": round(net_revenue, 2)
            }
        }
    except Exception as e:
        return {
            "database_connected": False,
            "error": str(e)
        }


@router.post("/api/tools/sql-query", response_model=SQLQueryResult)
def run_sql_query_tool(request: SQLQueryRequest, db: Session = Depends(get_db)):
    """
    Debug endpoint to execute a safe read-only SQL query via the SQL tool.
    """
    return execute_read_only_sql(db, request)


@router.get("/api/tools/sql-schema", response_model=SchemaContext)
def get_sql_schema_tool(db: Session = Depends(get_db)):
    """
    Debug endpoint to inspect the database schema context for future AI agent context.
    """
    return get_database_schema(db)


@router.post("/api/ask", response_model=AskResponse)
def ask_business_question(
    request: AskRequest,
    db: Session = Depends(get_db),
    provider: BaseLLMProvider = Depends(get_llm_provider)
):
    """
    Natural language decision intelligence endpoint.
    Orchestrates AI reasoning with safe tool calling, evidence assembly, decision intelligence analysis, and robustness testing.
    Supports single-turn initialization and multi-turn conversation continuation via investigation_id.
    Persists durable investigation turns and overall lifecycle state.
    """
    start_time = time.perf_counter()
    inv_record = None
    prior_turns = None

    if request.investigation_id:
        inv_record = InvestigationService.get_investigation_by_id(db=db, investigation_id=request.investigation_id)
        if not inv_record:
            raise HTTPException(status_code=404, detail=f"Investigation with ID '{request.investigation_id}' not found.")
        prior_turns = InvestigationService.list_recent_turns_for_investigation(db=db, investigation_id=request.investigation_id, limit=3)
        inv_id = request.investigation_id
    else:
        try:
            inv_record = InvestigationService.create_investigation(
                db=db,
                question=request.question
            )
        except Exception:
            pass
        inv_id = inv_record.investigation_id if inv_record else InvestigationService.generate_investigation_id()

    try:
        response = run_investigation_loop(
            question=request.question,
            db=db,
            provider=provider,
            max_turns=request.max_turns or 3,
            prior_turns=prior_turns
        )
        end_time = time.perf_counter()
        exec_ms = (end_time - start_time) * 1000.0

        if response.metadata is None:
            response.metadata = {}
        response.metadata["investigation_id"] = inv_id
        response.investigation_id = inv_id

        # Persist append-only InvestigationTurn
        try:
            InvestigationService.create_turn(
                db=db,
                investigation_id=inv_id,
                user_question=request.question,
                response=response,
                execution_time_ms=exec_ms
            )
        except Exception:
            pass

        if inv_record:
            try:
                if response.success:
                    InvestigationService.update_investigation_success(
                        db=db,
                        investigation_id=inv_id,
                        response=response,
                        execution_time_ms=exec_ms
                    )
                else:
                    InvestigationService.update_investigation_failure(
                        db=db,
                        investigation_id=inv_id,
                        error_message=response.error or "Investigation failed with empty response.",
                        execution_time_ms=exec_ms
                    )
            except Exception:
                pass

        return response

    except Exception as exc:
        end_time = time.perf_counter()
        exec_ms = (end_time - start_time) * 1000.0
        if inv_record:
            try:
                InvestigationService.update_investigation_failure(
                    db=db,
                    investigation_id=inv_id,
                    error_message=str(exc),
                    execution_time_ms=exec_ms
                )
            except Exception:
                pass
        raise


@router.get("/api/investigations", response_model=List[InvestigationSummary])
def list_investigations_history(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of records to return."),
    offset: int = Query(default=0, ge=0, description="Offset pagination index."),
    db: Session = Depends(get_db)
):
    """
    Retrieves lightweight investigation summaries ordered newest-first (created_at DESC).
    """
    records = InvestigationService.list_investigations(db=db, limit=limit, offset=offset)
    return [InvestigationSummary.model_validate(r) for r in records]


@router.get("/api/investigations/metrics/summary", response_model=InvestigationMetricsSummary)
def get_investigation_metrics_summary(
    db: Session = Depends(get_db)
):
    """
    Retrieves global investigation metrics summary including investigation counts,
    human review decision counts, robustness status distribution, and average execution time.
    """
    return InvestigationService.get_metrics_summary(db=db)


@router.get("/api/investigations/{investigation_id}", response_model=InvestigationDetail)
def get_investigation_detail(
    investigation_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves full investigation detail including stored AskResponse result_json, latest human review info,
    and ordered conversation turn history.
    Raises HTTP 404 if investigation record is not found.
    """
    record = InvestigationService.get_investigation_by_id(db=db, investigation_id=investigation_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Investigation with ID '{investigation_id}' not found.")

    detail = InvestigationDetail.model_validate(record)
    latest_rev = InvestigationService.get_latest_review(db=db, investigation_id=investigation_id)
    reviews = InvestigationService.list_reviews_for_investigation(db=db, investigation_id=investigation_id)
    turns = InvestigationService.list_turns_for_investigation(db=db, investigation_id=investigation_id)

    if latest_rev:
        detail.latest_review = InvestigationReviewResponse.model_validate(latest_rev)
    detail.review_count = len(reviews)
    detail.turns = [InvestigationTurnResponse.model_validate(t) for t in turns]

    return detail



@router.post("/api/investigations/{investigation_id}/reassess", response_model=InvestigationReassessResponse)
def reassess_investigation_robustness(
    investigation_id: str,
    request: InvestigationReassessRequest = InvestigationReassessRequest(),
    db: Session = Depends(get_db)
):
    """
    Deterministically re-evaluates multi-scenario metric robustness for an existing investigation
    using a caller-specified scenario shift percentage.
    Does NOT invoke the LLM provider or execute database SQL queries.
    """
    try:
        return InvestigationService.reassess_investigation(
            db=db,
            investigation_id=investigation_id,
            scenario_shift_pct=request.scenario_shift_pct
        )
    except ValueError as err:
        err_str = str(err)
        if "not found" in err_str.lower():
            raise HTTPException(status_code=404, detail=err_str)
        else:
            raise HTTPException(status_code=400, detail=err_str)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Re-assessment execution error: {str(exc)}")


@router.post("/api/investigations/{investigation_id}/review", response_model=InvestigationReviewResponse)
def create_investigation_review(
    investigation_id: str,
    request: InvestigationReviewCreate,
    db: Session = Depends(get_db)
):
    """
    Submits a persistent Human-in-the-Loop review decision (APPROVED, REJECTED, FLAGGED) for an investigation.
    Does NOT invoke the LLM provider or execute database SQL queries.
    Does NOT mutate original investigation result_json or robustness findings.
    """
    try:
        review_record = InvestigationService.create_review(
            db=db,
            investigation_id=investigation_id,
            review_data=request
        )
        return InvestigationReviewResponse.model_validate(review_record)
    except ValueError as err:
        err_str = str(err)
        if "not found" in err_str.lower():
            raise HTTPException(status_code=404, detail=err_str)
        elif "in_progress" in err_str.lower():
            raise HTTPException(status_code=400, detail=err_str)
        else:
            raise HTTPException(status_code=400, detail=err_str)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Review submission execution error: {str(exc)}")
