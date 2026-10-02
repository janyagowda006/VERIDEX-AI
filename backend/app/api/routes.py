import logging
from typing import List
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
    InvestigationDetailResponse,
    InvestigationReviewRequest,
)
from app.services.investigation_service import (
    InvestigationService,
    InvestigationNotFoundError,
    InvestigationValidationError,
)
from app.schemas.decomposition import DecompositionRequest, DecompositionResponse
from app.services.driver_decomposition import decompose_change
from app.schemas.campaign_impact import CampaignImpactRequest, CampaignImpactResponse
from app.services.campaign_impact import campaign_impact
from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.claim_checker import verify_answer
from app.ai.provider import BaseLLMProvider, get_llm_provider
from app.ai.orchestrator import run_investigation_loop

logger = logging.getLogger(__name__)

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


@router.post("/tools/decompose", response_model=DecompositionResponse)
@router.post("/api/tools/decompose", response_model=DecompositionResponse)
def decompose_revenue_change(
    request: DecompositionRequest,
    db: Session = Depends(get_db)
):
    """
    Deterministic driver decomposition tool explaining revenue changes between two periods.
    Decomposes changes hierarchically across region, category, segment, and customer.
    Enforces sum(driver_deltas) == total_change invariant and strictly excludes cancelled orders.
    """
    try:
        return decompose_change(
            db=db,
            metric=request.metric,
            period_a=request.period_a,
            period_b=request.period_b,
            dimensions=request.dimensions,
            top_n=request.top_n,
            include_baseline=request.include_baseline or False
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decomposition error: {str(e)}")


@router.post("/tools/campaign-impact", response_model=CampaignImpactResponse)
@router.post("/api/tools/campaign-impact", response_model=CampaignImpactResponse)
def evaluate_campaign_impact(
    request: CampaignImpactRequest,
    db: Session = Depends(get_db)
):
    """
    Deterministic Difference-in-Differences observational campaign impact analysis.
    Evaluates revenue impact between exposed and control cohorts across before and after periods.
    Always includes mandatory disclaimer: 'Observational evidence; causation not proven.'
    """
    try:
        return campaign_impact(
            db=db,
            campaign_id=request.campaign_id,
            min_sample_size=request.min_sample_size or 15
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Campaign impact error: {str(e)}")


@router.post("/verify", response_model=VerificationResponse)
@router.post("/api/verify", response_model=VerificationResponse)
def verify_llm_answer(
    request: VerificationRequest
):
    """
    Deterministic numerical answer verification endpoint (Task 3).
    Extracts every relevant numerical claim from an LLM-generated answer and verifies
    whether each claim is supported by the supplied structured evidence within tolerance.
    Enforces 'AI for reasoning, code for correctness':
    - Returns 'PASS' if and only if all numerical claims are verified against evidence.
    - Returns 'FAIL' if any numerical claim is unsupported.
    """
    try:
        return verify_answer(
            llm_text=request.llm_text,
            evidence_list=request.evidence_list,
            tolerance=request.tolerance if request.tolerance is not None else 0.05
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification error: {str(e)}")


@router.post("/api/ask", response_model=AskResponse)
def ask_business_question(
    request: AskRequest,
    db: Session = Depends(get_db),
    provider: BaseLLMProvider = Depends(get_llm_provider)
):
    """
    Natural language decision intelligence endpoint.
    Orchestrates AI reasoning with safe tool calling, evidence assembly, decision intelligence analysis, and robustness testing.
    Persists the resulting investigation lifecycle record using InvestigationService.
    """
    response = run_investigation_loop(
        question=request.question,
        db=db,
        provider=provider,
        max_turns=request.max_turns or 3
    )

    try:
        service = InvestigationService(db)
        inv = service.create_investigation(
            question=request.question,
            response=response
        )
        response.metadata["investigation_id"] = inv.investigation_id
    except Exception as e:
        logger.error("Failed to persist investigation for question '%s': %s", request.question, e)
        response.metadata["persistence_error"] = str(e)

    return response


@router.get("/api/investigations", response_model=List[InvestigationSummary])
def list_investigations(
    limit: int = Query(default=20, description="Maximum number of summaries to return (1-100)"),
    offset: int = Query(default=0, description="Offset index for pagination (>=0)"),
    db: Session = Depends(get_db)
):
    """
    Lists historical investigations with deterministic newest-first ordering and bounded pagination.
    Returns lightweight summaries without raw evidence payloads.
    """
    service = InvestigationService(db)
    try:
        return service.list_summaries(limit=limit, offset=offset)
    except (InvestigationValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/investigations/{investigation_id}", response_model=InvestigationDetailResponse)
def get_investigation_detail(
    investigation_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves complete investigation details, including reconstructed AskResponse and full audit trail.
    """
    service = InvestigationService(db)
    detail = service.get_investigation_detail(investigation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
    return detail


@router.post("/api/investigations/{investigation_id}/review", response_model=InvestigationDetailResponse)
def review_investigation(
    investigation_id: str,
    review_req: InvestigationReviewRequest,
    db: Session = Depends(get_db)
):
    """
    Records human executive review decision (APPROVED, REJECTED, FLAGGED) with reviewer notes.
    Appends an immutable entry to the investigation audit trail.
    """
    service = InvestigationService(db)
    try:
        service.update_review(
            investigation_id=investigation_id,
            review_decision=review_req.status,
            reviewer_notes=review_req.reviewer_notes
        )
    except InvestigationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvestigationValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    detail = service.get_investigation_detail(investigation_id)
    return detail


@router.get("/api/investigations/{investigation_id}/report", response_model=InvestigationDetailResponse)
def get_investigation_report(
    investigation_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns structured decision intelligence report for an investigation,
    reusing the validated InvestigationDetailResponse model.
    """
    service = InvestigationService(db)
    detail = service.get_investigation_detail(investigation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
    return detail
