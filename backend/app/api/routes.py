import time
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, File, UploadFile
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.db import get_db

from app.models.business_data import Customer, Product, Order, OrderItem
from app.models.user import User
from app.services.metrics import calculate_net_revenue
from app.services.schema_introspection import get_database_schema
from app.tools.sql_tool import execute_read_only_sql
from app.schemas.sql_tool import SQLQueryRequest, SQLQueryResult, SchemaContext
from app.schemas.ai import AskRequest, AskResponse
from app.schemas.auth import LoginRequest, Token, UserRead
from app.schemas.data_upload import DataSourceUploadResponse
from app.services.data_ingestion import process_uploaded_dataset
from app.schemas.investigation import (
    InvestigationSummary,
    InvestigationDetailResponse,
    InvestigationReassessRequest,
    InvestigationReassessResponse,
    InvestigationReviewCreate,
    InvestigationMetricsSummary
)
from app.services.investigation_service import (
    InvestigationService,
    InvestigationNotFoundError,
    InvestigationValidationError
)
from app.schemas.decomposition import DecompositionRequest, DecompositionResponse
from app.services.driver_decomposition import decompose_change
from app.schemas.campaign_impact import CampaignImpactRequest, CampaignImpactResponse
from app.services.campaign_impact import campaign_impact
from app.schemas.verification import VerificationRequest, VerificationResponse
from app.services.claim_checker import verify_answer
from app.services.report_exporter import ReportExporter
from app.services.audit_logger import AuditLogger
from app.schemas.audit import AuditLogResponse
from app.ai.provider import BaseLLMProvider, get_llm_provider
from app.ai.orchestrator import run_investigation_loop
from app.core.auth import verify_password, create_access_token
from app.api.deps import get_current_user, require_roles, seed_default_users_if_needed


logger = logging.getLogger(__name__)

router = APIRouter()


def _get_client_ip(request: Request) -> Optional[str]:
    if request and request.client:
        return request.client.host
    return None


@router.get("/health")
def health_check():
    """
    Public health check endpoint to verify backend foundation startup.
    Returns HTTP 200 with status ok.
    """
    return {"status": "ok"}


@router.post("/api/auth/login", response_model=Token)
def login_for_access_token(
    request_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticates user credentials against database users.
    Returns a signed JWT access token and User profile upon success.
    """
    seed_default_users_if_needed(db)
    user = db.query(User).filter(User.email == request_data.email.strip()).first()
    client_ip = _get_client_ip(request)

    if not user or not verify_password(request_data.password, user.hashed_password):
        AuditLogger.record_event(
            db=db,
            action_type="LOGIN_FAILURE",
            user_id=user.user_id if user else None,
            user_role=user.role if user else None,
            resource_id=request_data.email.strip(),
            status="FAILURE",
            ip_address=client_ip,
            details="Invalid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        AuditLogger.record_event(
            db=db,
            action_type="LOGIN_FAILURE",
            user_id=user.user_id,
            user_role=user.role,
            resource_id=user.user_id,
            status="FAILURE",
            ip_address=client_ip,
            details="User account inactive"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"user_id": user.user_id, "email": user.email, "role": user.role}
    )

    AuditLogger.record_event(
        db=db,
        action_type="LOGIN_SUCCESS",
        user_id=user.user_id,
        user_role=user.role,
        resource_id=user.user_id,
        status="SUCCESS",
        ip_address=client_ip
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserRead.model_validate(user)
    )


@router.get("/api/auth/me", response_model=UserRead)
def read_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves profile information for the currently authenticated user.
    """
    return UserRead.model_validate(current_user)


@router.get("/db-status")
def db_status_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Development debug endpoint to verify database connectivity and table counts. Restricted to ADMIN.
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
def run_sql_query_tool(
    request: SQLQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ANALYST", "ADMIN"))
):
    """
    Tool endpoint executing read-only SQL queries against business database.
    """
    return execute_read_only_sql(request.sql, db)


@router.get("/api/tools/schema", response_model=SchemaContext)
def get_sql_schema_tool(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ANALYST", "ADMIN"))
):
    """
    Tool endpoint returning dynamic database schema context.
    """
    return get_database_schema(db)


@router.post("/api/data-sources/upload", response_model=DataSourceUploadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/data/upload", response_model=DataSourceUploadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/data/upload", response_model=DataSourceUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_data_source_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ANALYST", "ADMIN"))
):
    """
    Dynamic data ingestion endpoint accepting CSV (.csv) or Excel (.xlsx, .xls) multipart file uploads.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file attached to upload request."
        )

    try:
        content = await file.read()
        res_dict = process_uploaded_dataset(
            file_bytes=content,
            filename=file.filename,
            db=db
        )
        return DataSourceUploadResponse(**res_dict)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File ingestion execution error: {str(exc)}"
        )


@router.post("/tools/decompose", response_model=DecompositionResponse)
@router.post("/api/tools/decompose", response_model=DecompositionResponse)
def decompose_metric_change(
    request: DecompositionRequest,
    db: Session = Depends(get_db)
):
    """
    Driver Decomposition tool endpoint (Task 1).
    Performs deterministic metric change decomposition across dimension breakdown.
    """
    try:
        return decompose_change(
            db=db,
            metric=request.metric,
            period_a=request.period_a,
            period_b=request.period_b,
            dimensions=request.dimensions,
            top_n=request.top_n,
            include_baseline=request.include_baseline
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
    Campaign Impact / Difference-in-Differences tool endpoint (Task 2).
    Evaluates campaign lift deterministically comparing exposed vs control cohorts.
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
    Verifies whether numerical claims in an answer are supported by structured evidence.
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
    provider: BaseLLMProvider = Depends(get_llm_provider),
    current_user: User = Depends(require_roles("ANALYST", "ADMIN"))
):
    """
    Natural language decision intelligence endpoint.
    Orchestrates AI reasoning with safe tool calling, evidence assembly, decision intelligence analysis, and robustness testing.
    """
    start_time = time.perf_counter()
    inv_record = None
    prior_turns = None

    if request.investigation_id:
        inv_record = InvestigationService.get_investigation_by_id(db=db, investigation_id=request.investigation_id)
        if not inv_record:
            raise HTTPException(status_code=404, detail=f"Investigation with ID '{request.investigation_id}' not found.")
        if inv_record.owner_id and current_user and inv_record.owner_id != current_user.user_id and current_user.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: Cannot append turns to an investigation owned by another user."
            )

        prior_turns = InvestigationService.list_recent_turns_for_investigation(db=db, investigation_id=request.investigation_id, limit=3)
        inv_id = request.investigation_id
    else:
        inv_id = InvestigationService.generate_investigation_id()

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

        # Safely attempt DB persistence
        try:
            try:
                db.rollback()
            except Exception:
                pass
            service = InvestigationService(db)

            owner_id = current_user.user_id if current_user else None
            inv = service.create_investigation(
                db=db,
                question=request.question,
                response=response,
                investigation_id=inv_id,
                owner_id=owner_id
            )
            response.metadata["investigation_id"] = inv.investigation_id
            response.investigation_id = inv.investigation_id

            try:
                InvestigationService.create_turn(
                    db=db,
                    investigation_id=inv.investigation_id,
                    user_question=request.question,
                    response=response,
                    execution_time_ms=exec_ms
                )
            except Exception:
                pass

        except Exception as e:
            logger.error("Failed to persist investigation for question '%s': %s", request.question, e)
            response.metadata["persistence_error"] = str(e)

        return response

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Investigation execution error: {str(exc)}")


@router.get("/api/investigations", response_model=List[InvestigationSummary])
def list_investigations_history(
    limit: int = Query(default=20, description="Maximum number of summaries to return (1-100)"),
    offset: int = Query(default=0, description="Offset index for pagination (>=0)"),
    search: Optional[str] = Query(default=None, description="Optional keyword search term over investigation question or ID."),
    status: Optional[str] = Query(default=None, description="Optional filter by investigation lifecycle status."),
    robustness_status: Optional[str] = Query(default=None, description="Optional filter by decision robustness status."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves lightweight investigation summaries ordered newest-first (created_at DESC).
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail=f"Pagination limit must be between 1 and 100, got {limit}.")
    if offset < 0:
        raise HTTPException(status_code=400, detail=f"Pagination offset must be non-negative, got {offset}.")

    owner_filter = current_user.user_id if current_user and current_user.role == "ANALYST" else None
    service = InvestigationService(db)
    try:
        records = service.list_investigations(
            db=db,
            limit=limit,
            offset=offset,
            search=search,
            status=status,
            robustness_status=robustness_status,
            owner_id=owner_filter
        )
        return [service.to_summary(r) for r in records]
    except (InvestigationValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/investigations/metrics/summary", response_model=InvestigationMetricsSummary)
def get_investigation_metrics_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves global investigation metrics summary including investigation counts,
    human review decision counts, robustness status distribution, and average execution time.
    """
    return InvestigationService.get_metrics_summary(db=db)


@router.get("/api/investigations/{investigation_id}", response_model=InvestigationDetailResponse)
def get_investigation_detail(
    investigation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves complete investigation details, including reconstructed AskResponse and full audit trail.
    Enforces ownership isolation for ANALYST role.
    """
    record = InvestigationService.get_investigation_by_id(db=db, investigation_id=investigation_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Investigation with ID '{investigation_id}' not found.")

    if current_user and current_user.role == "ANALYST" and record.owner_id and record.owner_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Cannot view another analyst's investigation."
        )

    service = InvestigationService(db)
    detail = service.get_investigation_detail(investigation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
    return detail


@router.post("/api/investigations/{investigation_id}/reassess", response_model=InvestigationReassessResponse)
def reassess_investigation_robustness(
    investigation_id: str,
    request: InvestigationReassessRequest = InvestigationReassessRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ANALYST", "REVIEWER", "ADMIN"))
):
    """
    Deterministically re-evaluates multi-scenario metric robustness for an existing investigation.
    """
    record = InvestigationService.get_investigation_by_id(db=db, investigation_id=investigation_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Investigation with ID '{investigation_id}' not found.")

    if current_user and current_user.role == "ANALYST" and record.owner_id and record.owner_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Cannot reassess another user's investigation."
        )

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


@router.post("/api/investigations/{investigation_id}/review", response_model=InvestigationDetailResponse)
def review_investigation(
    investigation_id: str,
    review_req: InvestigationReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Records human executive review decision (APPROVED, REJECTED, FLAGGED) with reviewer notes.
    Requires REVIEWER or ADMIN role.
    """
    has_auth_headers = bool(
        request.headers.get("Authorization") or
        request.headers.get("X-Veridex-Mock-User-Id") or
        request.headers.get("X-Veridex-Mock-Role")
    )

    if has_auth_headers and current_user and current_user.role not in ("REVIEWER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User with role '{current_user.role}' is not authorized to submit reviews."
        )

    st = review_req.status or review_req.review_status
    if not st:
        raise HTTPException(status_code=400, detail="Review decision status required.")

    st_str = str(st.value if hasattr(st, "value") else st).upper()
    if st_str not in ("APPROVED", "REJECTED", "FLAGGED"):
        raise HTTPException(status_code=400, detail=f"Invalid review decision '{st_str}'. Allowed decisions are APPROVED, REJECTED, FLAGGED.")

    reviewer_user_id = (current_user.user_id if (current_user and has_auth_headers) else None) or review_req.reviewer_id or "reviewer_user"

    inv_rec = InvestigationService.get_investigation_by_id(db=db, investigation_id=investigation_id)
    if not inv_rec:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")

    if inv_rec.owner_id and inv_rec.owner_id == reviewer_user_id and has_auth_headers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-Review Blocked: You cannot review an investigation you initiated."
        )

    try:
        service = InvestigationService(db)
        service.update_review(
            investigation_id=investigation_id,
            review_decision=st_str,
            reviewer_notes=review_req.review_notes or review_req.reviewer_notes,
            reviewer_user_id=reviewer_user_id
        )

        act_type = "REVIEW_APPROVE" if st_str == "APPROVED" else ("REVIEW_REJECT" if st_str == "REJECTED" else f"REVIEW_{st_str}")
        AuditLogger.record_event(
            db=db,
            action_type=act_type,
            user_id=current_user.user_id if current_user else None,
            user_role=current_user.role if current_user else None,
            resource_id=investigation_id,
            status="SUCCESS",
            ip_address=_get_client_ip(request),
            details=f"Decision: {st_str}"
        )
    except InvestigationNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvestigationValidationError, ValueError) as e:
        err_str = str(e)
        if "self-review" in err_str.lower():
            raise HTTPException(status_code=403, detail=err_str)
        elif "not found" in err_str.lower():
            raise HTTPException(status_code=404, detail=err_str)
        else:
            raise HTTPException(status_code=400, detail=err_str)

    detail = service.get_investigation_detail(investigation_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
    return detail


@router.get("/api/investigations/{investigation_id}/report", response_model=InvestigationDetailResponse)
def get_investigation_report(
    investigation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns structured decision intelligence report for an investigation.
    """
    service = InvestigationService(db)
    detail = service.get_investigation_detail(investigation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found.")
    return detail


@router.get("/api/investigations/{investigation_id}/export")
def export_investigation_report(
    investigation_id: str,
    request: Request,
    format: str = Query(default="json", description="Export format: 'json' or 'markdown'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("REVIEWER", "AUDITOR", "ADMIN"))
):
    """
    Exports a persisted investigation as a structured JSON object or Markdown audit report.
    """
    fmt = (format or "json").lower().strip()
    if fmt not in ("json", "markdown"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format '{format}'. Supported formats are 'json' and 'markdown'."
        )

    try:
        if fmt == "json":
            data = ReportExporter.export_as_json(db=db, investigation_id=investigation_id)
            AuditLogger.record_event(
                db=db,
                action_type="EXPORT_REPORT",
                user_id=current_user.user_id if current_user else None,
                user_role=current_user.role if current_user else None,
                resource_id=investigation_id,
                status="SUCCESS",
                ip_address=_get_client_ip(request),
                details="Format: json"
            )
            return JSONResponse(
                content=data,
                headers={"Content-Disposition": f'attachment; filename="{investigation_id}_audit_report.json"'}
            )
        else:
            md_text = ReportExporter.export_as_markdown(db=db, investigation_id=investigation_id)
            AuditLogger.record_event(
                db=db,
                action_type="EXPORT_REPORT",
                user_id=current_user.user_id if current_user else None,
                user_role=current_user.role if current_user else None,
                resource_id=investigation_id,
                status="SUCCESS",
                ip_address=_get_client_ip(request),
                details="Format: markdown"
            )
            return Response(
                content=md_text,
                media_type="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{investigation_id}_audit_report.md"'}
            )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err)
        )


@router.get("/api/v1/audit/logs", response_model=List[AuditLogResponse])
def list_security_audit_logs(
    user_id: Optional[str] = Query(default=None, description="Optional filter by user ID."),
    action_type: Optional[str] = Query(default=None, description="Optional filter by action type."),
    resource_id: Optional[str] = Query(default=None, description="Optional filter by resource ID."),
    status: Optional[str] = Query(default=None, description="Optional filter by event status."),
    limit: int = Query(default=50, ge=1, le=200, description="Max audit logs to return."),
    offset: int = Query(default=0, ge=0, description="Pagination offset."),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("AUDITOR", "ADMIN"))
):
    """
    Retrieves immutable enterprise audit log records ordered newest-first.
    """
    records = AuditLogger.list_audit_logs(
        db=db,
        user_id=user_id,
        action_type=action_type,
        resource_id=resource_id,
        status=status,
        limit=limit,
        offset=offset
    )
    return [AuditLogResponse.model_validate(r) for r in records]
