import time
import math
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.evidence import EvidenceItem, EvidenceType, DerivedFactCalculation
from app.services.evidence_calculations import EvidenceCalculator
from app.schemas.decomposition import (
    PeriodRange,
    DriverItem,
    WaterfallItem,
    DimensionDecomposition,
    DecompositionResponse
)


class ReconciliationError(ValueError):
    """
    Raised when sum of driver deltas does not reconcile with total change.
    """
    pass


# Strictly allow only revenue for Task 1
ALLOWED_METRICS = {"revenue"}

# Canonical dimensions and SQL projection mapping
DIMENSION_MAPPING: Dict[str, Dict[str, Any]] = {
    "region": {
        "canonical": "region",
        "sql_col": "c.region",
        "description": "Customer geographic region",
        "aliases": ["region", "regions", "geo", "geography"]
    },
    "category": {
        "canonical": "category",
        "sql_col": "p.category",
        "description": "Product category",
        "aliases": ["category", "categories", "product_category", "product category"]
    },
    "segment": {
        "canonical": "segment",
        "sql_col": "c.customer_segment",
        "description": "Customer market segment",
        "aliases": ["segment", "segments", "customer_segment", "customer segment"]
    },
    "customer": {
        "canonical": "customer",
        "sql_col": "c.customer_name",
        "description": "Customer account name",
        "aliases": ["customer", "customers", "customer_name", "customer name"]
    }
}

DEFAULT_HIERARCHICAL_DIMENSIONS = ["region", "category", "segment", "customer"]


def resolve_dimension(dim_raw: str) -> str:
    """
    Resolves raw dimension string against allowed dimensions or raises ValueError.
    Guards against SQL injection and invalid column references.
    """
    normalized = dim_raw.strip().lower()
    for canonical, config in DIMENSION_MAPPING.items():
        if normalized == canonical or normalized in config["aliases"]:
            return canonical
    allowed_list = list(DIMENSION_MAPPING.keys())
    raise ValueError(
        f"Invalid dimension '{dim_raw}'. Allowed dimensions are: {allowed_list}"
    )


def normalize_period(period_input: Any) -> PeriodRange:
    """
    Normalizes any supported period input into a validated PeriodRange object.
    """
    if isinstance(period_input, PeriodRange):
        return period_input
    if isinstance(period_input, dict):
        return PeriodRange(**period_input)
    if isinstance(period_input, (list, tuple)) and len(period_input) == 2:
        return PeriodRange(start_date=str(period_input[0]), end_date=str(period_input[1]))
    if isinstance(period_input, str):
        cleaned = period_input.replace(" to ", ":").replace("/", "-")
        if ":" in cleaned:
            parts = cleaned.split(":")
            return PeriodRange(start_date=parts[0].strip(), end_date=parts[1].strip())
    raise ValueError(f"Unable to parse period: {period_input}")


def query_period_total_revenue(db: Session, start_date: str, end_date: str) -> float:
    """
    Computes total verified revenue for a period, strictly excluding status='cancelled'.
    Uses parameterized SQL and ensures read-only semantics.
    """
    query = text(
        """
        SELECT COALESCE(SUM(oi.quantity * oi.unit_price * (1.0 - COALESCE(o.discount, 0.0))), 0.0) AS total_revenue
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE LOWER(o.order_status) != :cancelled_status
          AND o.order_date >= :start_date
          AND o.order_date <= :end_date
        """
    )
    result = db.execute(
        query,
        {
            "cancelled_status": "cancelled",
            "start_date": start_date,
            "end_date": end_date
        }
    ).scalar()
    return round(float(result), 2) if result is not None else 0.0


def query_dimension_revenues(
    db: Session,
    dimension_canonical: str,
    start_date: str,
    end_date: str
) -> Dict[str, float]:
    """
    Queries aggregated revenue grouped by the verified dimension column.
    Excludes status='cancelled' orders.
    Uses parameterized SQL and safe AST-mapped column identifier.
    """
    sql_col = DIMENSION_MAPPING[dimension_canonical]["sql_col"]
    query_str = f"""
        SELECT 
            {sql_col} AS group_label,
            COALESCE(SUM(oi.quantity * oi.unit_price * (1.0 - COALESCE(o.discount, 0.0))), 0.0) AS revenue
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE LOWER(o.order_status) != :cancelled_status
          AND o.order_date >= :start_date
          AND o.order_date <= :end_date
        GROUP BY {sql_col}
        ORDER BY revenue DESC
    """
    results = db.execute(
        text(query_str),
        {
            "cancelled_status": "cancelled",
            "start_date": start_date,
            "end_date": end_date
        }
    ).fetchall()

    rev_map: Dict[str, float] = {}
    for row in results:
        label = str(row[0]) if row[0] is not None else "Unknown"
        rev = round(float(row[1]), 2) if row[1] is not None else 0.0
        rev_map[label] = rev
    return rev_map


def decompose_change(
    db: Session,
    metric: str,
    period_a: Any,
    period_b: Any,
    dimensions: Optional[List[str]] = None,
    top_n: Optional[int] = 10,
    include_baseline: bool = False
) -> DecompositionResponse:
    """
    Deterministically explains why revenue changed between two periods.

    Explicit standard dependency signature:
    - db: SQLAlchemy Session (managed by dependency injection)
    - metric: Initial supported: 'revenue'
    - period_a: Date range for baseline comparison period
    - period_b: Date range for comparison period
    - dimensions: List of dimensions to evaluate independently (region, category, segment, customer)
    - top_n: Top N driver cutoff for high-cardinality dimensions (e.g. customer)
    - include_baseline: Whether to include baseline milestones in top-level waterfall

    Guarantees:
    - sum(driver_deltas) == total_change invariant enforced per dimension
    - Independent dimension attribution (each dimension independently reconciles to total_change)
    - Top-level waterfall uses single primary dimension (no double counting)
    - Parameterized SQL execution
    - Excludes order_status = 'cancelled' (case-insensitive)
    - Deterministic zero-baseline semantics (null for new, -100% for lost, 0% for zero/zero)
    - Integrates with VERIDEX evidence architecture
    """
    start_time = time.perf_counter()

    # Metric validation (strictly 'revenue')
    norm_metric = metric.strip().lower()
    if norm_metric not in ALLOWED_METRICS:
        raise ValueError(f"Unsupported metric '{metric}'. Supported metrics are: {list(ALLOWED_METRICS)}")

    # Period validation
    p_a = normalize_period(period_a)
    p_b = normalize_period(period_b)

    # Dimensions validation
    if dimensions is None or len(dimensions) == 0:
        canonical_dims = list(DEFAULT_HIERARCHICAL_DIMENSIONS)
    else:
        canonical_dims = [resolve_dimension(d) for d in dimensions]

    # PostgreSQL transaction-level read-only enforcement
    # Note: Executed conditionally when running against PostgreSQL databases.
    # SQLite (used in automated unit tests) does not support SET TRANSACTION READ ONLY.
    dialect_name = db.bind.dialect.name if hasattr(db, "bind") and db.bind else ""
    if dialect_name in ["postgres", "postgresql"]:
        try:
            db.execute(text("SET TRANSACTION READ ONLY"))
            db.execute(text("SET LOCAL statement_timeout = '3000ms'"))
        except Exception:
            pass

    # 1. Calculate Period A and Period B total revenue
    rev_a = query_period_total_revenue(db, p_a.start_date, p_a.end_date)
    rev_b = query_period_total_revenue(db, p_b.start_date, p_b.end_date)
    total_change = round(rev_b - rev_a, 2)

    overall_pct_change: Optional[float] = None
    if rev_a != 0.0:
        overall_pct_change = round(((rev_b - rev_a) / rev_a) * 100.0, 2)
    elif rev_b > 0.0:
        overall_pct_change = None  # Undefined percentage growth from zero baseline
    elif rev_b == 0.0:
        overall_pct_change = 0.0

    breakdowns: Dict[str, DimensionDecomposition] = {}
    all_evidence: List[EvidenceItem] = []
    evidence_calculator = EvidenceCalculator()

    primary_dim = canonical_dims[0] if canonical_dims else "region"

    for dim in canonical_dims:
        groups_a = query_dimension_revenues(db, dim, p_a.start_date, p_a.end_date)
        groups_b = query_dimension_revenues(db, dim, p_b.start_date, p_b.end_date)

        all_labels = set(groups_a.keys()) | set(groups_b.keys())
        raw_drivers: List[DriverItem] = []

        for label in all_labels:
            g_a = groups_a.get(label, 0.0)
            g_b = groups_b.get(label, 0.0)
            delta = round(g_b - g_a, 2)

            # Strict deterministic zero-baseline semantics
            if g_a == 0.0 and g_b > 0.0:
                status = "new"
                pct_within = None  # null in JSON: growth from zero is mathematically undefined
            elif g_a > 0.0 and g_b == 0.0:
                status = "lost"
                pct_within = -100.0
            elif g_a == 0.0 and g_b == 0.0:
                status = "normal"
                pct_within = 0.0
            else:
                status = "normal"
                pct_within = round(((g_b - g_a) / g_a) * 100.0, 2)

            # Percent of total change (avoid zero division if total_change == 0)
            if total_change != 0.0:
                pct_total = round((delta / total_change) * 100.0, 2)
            else:
                pct_total = 0.0

            raw_drivers.append(DriverItem(
                label=label,
                dimension=dim,
                revenue_a=g_a,
                revenue_b=g_b,
                delta_amount=delta,
                percent_of_total_change=pct_total,
                percent_change_within_group=pct_within,
                status=status
            ))

        # Handle top N grouping for customer dimension (or high cardinality)
        if dim == "customer" and top_n and len(raw_drivers) > top_n:
            # Sort by absolute delta descending to preserve major drivers
            sorted_by_impact = sorted(raw_drivers, key=lambda d: abs(d.delta_amount), reverse=True)
            top_drivers = sorted_by_impact[:top_n]
            remaining = sorted_by_impact[top_n:]

            other_a = round(sum(d.revenue_a for d in remaining), 2)
            other_b = round(sum(d.revenue_b for d in remaining), 2)
            other_delta = round(other_b - other_a, 2)

            if other_a == 0.0 and other_b > 0.0:
                other_status = "new"
                other_pct_within = None
            elif other_a > 0.0 and other_b == 0.0:
                other_status = "lost"
                other_pct_within = -100.0
            elif other_a == 0.0 and other_b == 0.0:
                other_status = "normal"
                other_pct_within = 0.0
            else:
                other_status = "normal"
                other_pct_within = round(((other_b - other_a) / other_a) * 100.0, 2)

            if total_change != 0.0:
                other_pct_total = round((other_delta / total_change) * 100.0, 2)
            else:
                other_pct_total = 0.0

            other_driver = DriverItem(
                label="Other (Remaining Customers)",
                dimension=dim,
                revenue_a=other_a,
                revenue_b=other_b,
                delta_amount=other_delta,
                percent_of_total_change=other_pct_total,
                percent_change_within_group=other_pct_within,
                status=other_status
            )
            final_drivers = top_drivers + [other_driver]
        else:
            final_drivers = raw_drivers

        # Sort drivers: primary negative drivers first (decline), then positive growth drivers
        final_drivers.sort(key=lambda d: (d.delta_amount > 0, d.delta_amount))

        # INVARIANT ENFORCEMENT: sum(driver_deltas) == total_change
        sum_deltas = round(sum(d.delta_amount for d in final_drivers), 2)
        tolerance = 0.05  # 5 cents tolerance for rounding distribution across multiple groups

        reconciled = math.isclose(sum_deltas, total_change, abs_tol=tolerance)
        if not reconciled:
            raise ReconciliationError(
                f"Reconciliation invariant failed for dimension '{dim}': "
                f"sum(driver_deltas)={sum_deltas:.2f} != total_change={total_change:.2f} "
                f"(discrepancy {abs(sum_deltas - total_change):.4f} > tolerance {tolerance})"
            )

        # Build dimension waterfall chart JSON (independently reconciling for this dimension)
        dim_waterfall: List[WaterfallItem] = []
        cum_delta = 0.0
        for d in final_drivers:
            cum_delta = round(cum_delta + d.delta_amount, 2)
            dim_waterfall.append(WaterfallItem(
                label=d.label,
                value=d.delta_amount,
                cumulative=cum_delta
            ))

        breakdowns[dim] = DimensionDecomposition(
            dimension=dim,
            drivers=final_drivers,
            sum_driver_deltas=sum_deltas,
            reconciled=reconciled,
            waterfall=dim_waterfall
        )

        # Generate DERIVED_FACT evidence for drivers conforming to VERIDEX Evidence Architecture
        for d in final_drivers:
            ev_id = evidence_calculator.generate_evidence_id(prefix=f"ev_derived_{dim}")
            all_evidence.append(EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=(
                    f"Decomposition driver '{d.label}' ({dim}): delta of {d.delta_amount:+.2f} "
                    f"represents {d.percent_of_total_change:.2f}% of total change ({total_change:+.2f})."
                ),
                calculation=DerivedFactCalculation(
                    formula_name=f"{dim}_contribution_percentage",
                    formula=f"({dim}_delta / total_delta) * 100",
                    inputs={
                        f"{dim}_delta": d.delta_amount,
                        "total_delta": total_change,
                        "revenue_a": d.revenue_a,
                        "revenue_b": d.revenue_b,
                        "group_label": d.label
                    },
                    output=d.percent_of_total_change,
                    input_evidence_ids=[]
                ),
                limitations=[
                    "Revenue calculation strictly excludes orders where order_status = 'cancelled' (case-insensitive)."
                ]
            ))

    # Top-level waterfall strictly uses primary dimension (no concatenation across dimensions)
    primary_breakdown = breakdowns[primary_dim]
    top_level_waterfall = list(primary_breakdown.waterfall)

    # Full revenue bridge waterfall (Baseline -> Drivers -> Ending Total)
    bridge_waterfall: List[WaterfallItem] = [
        WaterfallItem(label="Period A Baseline", value=rev_a, cumulative=rev_a)
    ]
    bridge_running = rev_a
    for d in primary_breakdown.drivers:
        bridge_running = round(bridge_running + d.delta_amount, 2)
        bridge_waterfall.append(WaterfallItem(
            label=d.label,
            value=d.delta_amount,
            cumulative=bridge_running
        ))
    bridge_waterfall.append(WaterfallItem(label="Period B Total", value=0.0, cumulative=rev_b))

    exec_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return DecompositionResponse(
        success=True,
        metric=metric,
        period_a={"start_date": p_a.start_date, "end_date": p_a.end_date},
        period_b={"start_date": p_b.start_date, "end_date": p_b.end_date},
        total_revenue_a=rev_a,
        total_revenue_b=rev_b,
        total_change=total_change,
        percent_change=overall_pct_change,
        dimensions=canonical_dims,
        primary_dimension=primary_dim,
        breakdowns=breakdowns,
        waterfall=top_level_waterfall,
        revenue_bridge=bridge_waterfall,
        evidence=all_evidence,
        assumptions=[
            "Revenue calculation strictly excludes orders where order_status = 'cancelled' (case-insensitive).",
            "Net revenue formula applied: sum(quantity * unit_price * (1 - COALESCE(discount, 0.0))).",
            "Reconciliation invariant enforced: sum(driver_deltas) == total_change within tolerance.",
            "Decompositions across dimensions (region, category, segment, customer) represent independent attribution views."
        ],
        reconciliation_tolerance=0.05,
        execution_metadata={
            "execution_time_ms": exec_time_ms,
            "dimensions_evaluated": len(canonical_dims),
            "total_drivers_identified": sum(len(b.drivers) for b in breakdowns.values())
        }
    )
