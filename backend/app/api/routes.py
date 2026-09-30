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
from app.schemas.investigation import InvestigationSummary, InvestigationDetail
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
    Persists durable investigation lifecycle state (IN_PROGRESS -> COMPLETED / REQUIRES_REVIEW / FAILED).
    """
    start_time = time.perf_counter()
    inv_record = None

    # Step 1. Persist IN_PROGRESS investigation record
    try:
        inv_record = InvestigationService.create_investigation(
            db=db,
            question=request.question
        )
    except Exception:
        pass

    inv_id = inv_record.investigation_id if inv_record else InvestigationService.generate_investigation_id()

    # Step 2. Execute Orchestration Loop
    try:
        response = run_investigation_loop(
            question=request.question,
            db=db,
            provider=provider,
            max_turns=request.max_turns or 3
        )
        end_time = time.perf_counter()
        exec_ms = (end_time - start_time) * 1000.0

        # Attach investigation_id to metadata
        if response.metadata is None:
            response.metadata = {}
        response.metadata["investigation_id"] = inv_id

        # Step 3. Persist lifecycle completion status
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


@router.get("/api/investigations/{investigation_id}", response_model=InvestigationDetail)
def get_investigation_detail(
    investigation_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves full investigation detail including stored AskResponse result_json by investigation_id.
    Raises HTTP 404 if investigation record is not found.
    """
    record = InvestigationService.get_investigation_by_id(db=db, investigation_id=investigation_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Investigation with ID '{investigation_id}' not found.")
    return InvestigationDetail.model_validate(record)
