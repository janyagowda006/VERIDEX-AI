import math
import time
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.evidence import (
    EvidenceItem,
    EvidenceType,
    DerivedFactCalculation
)
from app.services.evidence_calculations import EvidenceCalculator
from app.schemas.campaign_impact import CampaignImpactResponse


# =====================================================================
# CAMPAIGN REGISTRY & METADATA CONFIGURATION
# =====================================================================
# NOTE ON CAMPAIGN REGISTRY:
# The VERIDEX production business database does NOT contain a native campaigns table,
# campaign foreign keys, or promotional tags. The registry below is a deterministic,
# code-level analytical configuration containing synthetic/demo campaign definitions
# used exclusively to exercise and demonstrate the Difference-in-Differences analytical capability.
# These definitions DO NOT represent discovered real business campaigns or claim that
# historical regional variations were caused by marketing campaigns.
# =====================================================================

@dataclass(frozen=True)
class CampaignDefinition:
    """
    Deterministic metadata definition for a demonstration/synthetic campaign.
    """
    campaign_id: str
    name: str
    region: str
    exposure_window: Tuple[date, date]
    before_window: Tuple[date, date]
    after_window: Tuple[date, date]
    description: str = ""


# Default deterministic demonstration registry
CAMPAIGN_REGISTRY: Dict[str, CampaignDefinition] = {
    "CMP-2025-Q3-SOUTH": CampaignDefinition(
        campaign_id="CMP-2025-Q3-SOUTH",
        name="Synthetic Demo Q3 South Campaign",
        region="South",
        exposure_window=(date(2025, 7, 1), date(2025, 9, 30)),
        before_window=(date(2025, 4, 1), date(2025, 6, 30)),
        after_window=(date(2025, 10, 1), date(2025, 12, 31)),
        description="Synthetic demonstration campaign metadata used to evaluate Difference-in-Differences analytical capability in South region."
    )
}


def register_campaign(definition: CampaignDefinition) -> None:
    """
    Registers a campaign definition into the in-memory registry (useful for isolated unit testing).
    """
    CAMPAIGN_REGISTRY[definition.campaign_id] = definition


def get_campaign(campaign_id: str) -> CampaignDefinition:
    """
    Retrieves campaign definition by ID or raises ValueError.
    """
    if campaign_id not in CAMPAIGN_REGISTRY:
        available = list(CAMPAIGN_REGISTRY.keys())
        raise ValueError(f"Campaign '{campaign_id}' not found in campaign registry. Available campaigns: {available}")
    return CAMPAIGN_REGISTRY[campaign_id]


# =====================================================================
# CORE DETERMINISTIC CALCULATION
# =====================================================================

def campaign_impact(
    db: Session,
    campaign_id: str,
    min_sample_size: int = 15,
    custom_definition: Optional[CampaignDefinition] = None,
) -> CampaignImpactResponse:
    """
    Calculates deterministic Difference-in-Differences (DiD) observational impact for a campaign.

    CORE PRINCIPLE:
    'AI for reasoning, code for correctness.'
    All numerical averages, changes, DiD estimates, variability, and inferences
    originate strictly from deterministic SQL and Python computation.

    EXPOSURE COHORT:
    Customers in the campaign region who placed at least one qualifying completed order
    during the campaign exposure window.

    CONTROL COHORT:
    Customers in the same campaign region who did NOT place a qualifying order during the
    campaign exposure window, while having qualifying order history for the before/after analysis.

    DISCLAIMER:
    Always returns: 'Observational evidence; causation not proven.'

    Parameters:
    - db: SQLAlchemy Session
    - campaign_id: Identifier of the campaign to evaluate
    - min_sample_size: Minimum customer sample size per group (default 15)
    - custom_definition: Optional CampaignDefinition override (e.g. for synthetic unit tests)
    """
    start_time = time.perf_counter()

    # Enforce read-only transaction on PostgreSQL
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET statement_timeout = 3000"))

    campaign = custom_definition or get_campaign(campaign_id)
    calc = EvidenceCalculator()

    exp_start, exp_end = campaign.exposure_window
    bef_start, bef_end = campaign.before_window
    aft_start, aft_end = campaign.after_window

    # -------------------------------------------------------------
    # Step 1: Identify Exposed Customer Cohort
    # -------------------------------------------------------------
    # Customers in target region with >=1 completed order in exposure window
    sql_exposed = text("""
        SELECT DISTINCT c.customer_id
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE c.region = :region
          AND o.order_date >= :exp_start
          AND o.order_date <= :exp_end
          AND LOWER(o.order_status) != 'cancelled'
        ORDER BY c.customer_id ASC
    """)
    exposed_rows = db.execute(sql_exposed, {
        "region": campaign.region,
        "exp_start": exp_start.strftime("%Y-%m-%d"),
        "exp_end": exp_end.strftime("%Y-%m-%d")
    }).fetchall()
    exposed_customer_ids = [r[0] for r in exposed_rows]
    exposed_set = set(exposed_customer_ids)

    # -------------------------------------------------------------
    # Step 2: Identify Control Customer Cohort
    # -------------------------------------------------------------
    # Customers in same region who did NOT order in exposure window,
    # but have qualifying orders in before/after analysis periods
    sql_control = text("""
        SELECT DISTINCT c.customer_id
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE c.region = :region
          AND LOWER(o.order_status) != 'cancelled'
          AND (
              (o.order_date >= :bef_start AND o.order_date <= :bef_end)
              OR
              (o.order_date >= :aft_start AND o.order_date <= :aft_end)
          )
        ORDER BY c.customer_id ASC
    """)
    control_candidates = db.execute(sql_control, {
        "region": campaign.region,
        "bef_start": bef_start.strftime("%Y-%m-%d"),
        "bef_end": bef_end.strftime("%Y-%m-%d"),
        "aft_start": aft_start.strftime("%Y-%m-%d"),
        "aft_end": aft_end.strftime("%Y-%m-%d")
    }).fetchall()
    control_customer_ids = [r[0] for r in control_candidates if r[0] not in exposed_set]

    exposed_n = len(exposed_customer_ids)
    control_n = len(control_customer_ids)

    # -------------------------------------------------------------
    # Step 3: Compute Customer-Level Revenues for Before and After Periods
    # -------------------------------------------------------------
    def get_customer_revenues(
        customer_ids: List[str],
        start_dt: date,
        end_dt: date
    ) -> Dict[str, float]:
        """
        Calculates customer-level net revenue for a given date window.
        Returns a dictionary mapping customer_id -> total revenue.
        Uses exact repository revenue formula: quantity * unit_price * (1 - discount).
        """
        if not customer_ids:
            return {}

        # Parameterized query in chunks of 500 if cohort is large
        results: Dict[str, float] = {cid: 0.0 for cid in customer_ids}
        chunk_size = 500
        for i in range(0, len(customer_ids), chunk_size):
            chunk = customer_ids[i:i + chunk_size]
            param_names = [f"c_{idx}" for idx in range(len(chunk))]
            placeholders = ", ".join(f":{p}" for p in param_names)
            params = {
                "start_dt": start_dt.strftime("%Y-%m-%d"),
                "end_dt": end_dt.strftime("%Y-%m-%d"),
            }
            params.update({p: cid for p, cid in zip(param_names, chunk)})

            sql_rev = text(f"""
                SELECT
                    o.customer_id,
                    SUM(oi.quantity * oi.unit_price * (1.0 - COALESCE(o.discount, 0.0))) AS total_rev
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                WHERE o.customer_id IN ({placeholders})
                  AND o.order_date >= :start_dt
                  AND o.order_date <= :end_dt
                  AND LOWER(o.order_status) != 'cancelled'
                GROUP BY o.customer_id
            """)
            rows = db.execute(sql_rev, params).fetchall()
            for r in rows:
                results[r[0]] = float(r[1]) if r[1] is not None else 0.0

        return results

    # Customer revenues
    exp_rev_before_map = get_customer_revenues(exposed_customer_ids, bef_start, bef_end)
    exp_rev_after_map = get_customer_revenues(exposed_customer_ids, aft_start, aft_end)
    ctrl_rev_before_map = get_customer_revenues(control_customer_ids, bef_start, bef_end)
    ctrl_rev_after_map = get_customer_revenues(control_customer_ids, aft_start, aft_end)

    # Convert to aligned customer vectors
    exp_before_vals = [exp_rev_before_map[cid] for cid in exposed_customer_ids]
    exp_after_vals = [exp_rev_after_map[cid] for cid in exposed_customer_ids]
    ctrl_before_vals = [ctrl_rev_before_map[cid] for cid in control_customer_ids]
    ctrl_after_vals = [ctrl_rev_after_map[cid] for cid in control_customer_ids]

    # Calculate deterministic averages
    exposed_before = round(sum(exp_before_vals) / exposed_n, 2) if exposed_n > 0 else 0.0
    exposed_after = round(sum(exp_after_vals) / exposed_n, 2) if exposed_n > 0 else 0.0
    control_before = round(sum(ctrl_before_vals) / control_n, 2) if control_n > 0 else 0.0
    control_after = round(sum(ctrl_after_vals) / control_n, 2) if control_n > 0 else 0.0

    exposed_change = round(exposed_after - exposed_before, 2)
    control_change = round(control_after - control_before, 2)
    did = round(exposed_change - control_change, 2)

    # -------------------------------------------------------------
    # Step 4: Deterministic Control Group Variability
    # -------------------------------------------------------------
    # Customer-level change: d_j = rev_{j, after} - rev_{j, before}
    ctrl_diffs = [
        ctrl_after_vals[i] - ctrl_before_vals[i]
        for i in range(control_n)
    ]
    if control_n > 1:
        mean_ctrl_diff = sum(ctrl_diffs) / control_n
        ctrl_variance = sum((d - mean_ctrl_diff) ** 2 for d in ctrl_diffs) / (control_n - 1)
        ctrl_sd = math.sqrt(ctrl_variance)
        control_se = round(ctrl_sd / math.sqrt(control_n), 4)
    else:
        control_se = 0.0

    # -------------------------------------------------------------
    # Step 5: Deterministic Status and Inference Evaluation
    # -------------------------------------------------------------
    has_sufficient_sample = (exposed_n >= min_sample_size) and (control_n >= min_sample_size)
    status = "SUCCESS" if has_sufficient_sample else "INSUFFICIENT_DATA"

    if not has_sufficient_sample:
        inference = "Not supported"
    else:
        # Analytical classification rules (strictly non-causal)
        if did > 0 and abs(did) >= 1.96 * control_se:
            inference = "Supported by evidence"
        elif did > 0 and abs(did) < 1.96 * control_se:
            inference = "Weak support"
        else:
            inference = "Not supported"

    # -------------------------------------------------------------
    # Step 6: Evidence Generation (Taxonomy: DERIVED_FACT)
    # -------------------------------------------------------------
    common_limitations = [
        "Observational evidence; causation not proven.",
        "Control membership is observational and may be subject to selection bias because exposure is defined from observed ordering behavior.",
        "Revenue excludes cancelled orders (LOWER(order_status) = 'cancelled').",
        "Customer-level cohort averaging maintains constant customer set across before and after periods."
    ]

    evidence_items: List[EvidenceItem] = []

    # 1. Exposed Before Evidence
    evidence_items.append(EvidenceItem(
        evidence_id=calc.generate_evidence_id(prefix="ev_derived_exp_before"),
        evidence_type=EvidenceType.DERIVED_FACT,
        description=f"Exposed cohort before-period average revenue: ₹{exposed_before:.2f} across {exposed_n} customers.",
        calculation=DerivedFactCalculation(
            formula_name="average_revenue_per_customer",
            formula="sum(customer_revenue_before) / N_exposed",
            inputs={
                "customer_count": exposed_n,
                "total_revenue": round(sum(exp_before_vals), 2),
                "period": "before",
                "cohort": "exposed"
            },
            output=exposed_before,
            input_evidence_ids=[]
        ),
        limitations=common_limitations
    ))

    # 2. Exposed After Evidence
    evidence_items.append(EvidenceItem(
        evidence_id=calc.generate_evidence_id(prefix="ev_derived_exp_after"),
        evidence_type=EvidenceType.DERIVED_FACT,
        description=f"Exposed cohort after-period average revenue: ₹{exposed_after:.2f} across {exposed_n} customers.",
        calculation=DerivedFactCalculation(
            formula_name="average_revenue_per_customer",
            formula="sum(customer_revenue_after) / N_exposed",
            inputs={
                "customer_count": exposed_n,
                "total_revenue": round(sum(exp_after_vals), 2),
                "period": "after",
                "cohort": "exposed"
            },
            output=exposed_after,
            input_evidence_ids=[]
        ),
        limitations=common_limitations
    ))

    # 3. Control Before Evidence
    evidence_items.append(EvidenceItem(
        evidence_id=calc.generate_evidence_id(prefix="ev_derived_ctrl_before"),
        evidence_type=EvidenceType.DERIVED_FACT,
        description=f"Control cohort before-period average revenue: ₹{control_before:.2f} across {control_n} customers.",
        calculation=DerivedFactCalculation(
            formula_name="average_revenue_per_customer",
            formula="sum(customer_revenue_before) / N_control",
            inputs={
                "customer_count": control_n,
                "total_revenue": round(sum(ctrl_before_vals), 2),
                "period": "before",
                "cohort": "control"
            },
            output=control_before,
            input_evidence_ids=[]
        ),
        limitations=common_limitations
    ))

    # 4. Control After Evidence
    evidence_items.append(EvidenceItem(
        evidence_id=calc.generate_evidence_id(prefix="ev_derived_ctrl_after"),
        evidence_type=EvidenceType.DERIVED_FACT,
        description=f"Control cohort after-period average revenue: ₹{control_after:.2f} across {control_n} customers.",
        calculation=DerivedFactCalculation(
            formula_name="average_revenue_per_customer",
            formula="sum(customer_revenue_after) / N_control",
            inputs={
                "customer_count": control_n,
                "total_revenue": round(sum(ctrl_after_vals), 2),
                "period": "after",
                "cohort": "control"
            },
            output=control_after,
            input_evidence_ids=[]
        ),
        limitations=common_limitations
    ))

    # 5. Exposed Change Evidence
    evidence_items.append(EvidenceItem(
        evidence_id=calc.generate_evidence_id(prefix="ev_derived_exp_change"),
        evidence_type=EvidenceType.DERIVED_FACT,
        description=f"Exposed cohort change in average revenue: ₹{exposed_change:+.2f}.",
        calculation=DerivedFactCalculation(
            formula_name="cohort_change",
            formula="exposed_after - exposed_before",
            inputs={
                "exposed_before": exposed_before,
                "exposed_after": exposed_after
            },
            output=exposed_change,
            input_evidence_ids=[]
        ),
        limitations=common_limitations
    ))

    # 6. Control Change Evidence
    evidence_items.append(EvidenceItem(
        evidence_id=calc.generate_evidence_id(prefix="ev_derived_ctrl_change"),
        evidence_type=EvidenceType.DERIVED_FACT,
        description=f"Control cohort change in average revenue: ₹{control_change:+.2f}.",
        calculation=DerivedFactCalculation(
            formula_name="cohort_change",
            formula="control_after - control_before",
            inputs={
                "control_before": control_before,
                "control_after": control_after
            },
            output=control_change,
            input_evidence_ids=[]
        ),
        limitations=common_limitations
    ))

    # 7. DiD Evidence
    evidence_items.append(EvidenceItem(
        evidence_id=calc.generate_evidence_id(prefix="ev_derived_did"),
        evidence_type=EvidenceType.DERIVED_FACT,
        description=f"Difference-in-Differences estimate: ₹{did:+.2f} (SE: {control_se:.4f}).",
        calculation=DerivedFactCalculation(
            formula_name="difference_in_differences",
            formula="exposed_change - control_change",
            inputs={
                "exposed_change": exposed_change,
                "control_change": control_change,
                "control_se": control_se
            },
            output=did,
            input_evidence_ids=[]
        ),
        limitations=common_limitations
    ))

    # Research validation checks
    what_would_change_my_mind = [
        "Validate pre-campaign parallel trends across multiple historical baseline periods to verify pre-treatment trajectory alignment.",
        "Repeat analysis using an alternative comparable control population (e.g., matching or cross-regional control cohort).",
        "Test sensitivity of DiD estimates to alternative campaign window bounds and customer qualification thresholds."
    ]

    assumptions = [
        "Observational cohort analysis; causation not proven.",
        "Control membership is observational and may be subject to selection bias because exposure is defined from observed ordering behavior.",
        "Campaign definition is an analytical demonstration configuration; no native campaign table exists in the production database.",
        "Exposed population: Customers in target region with >=1 completed order during the exposure window.",
        "Control population: Customers in target region with no completed orders during exposure window but qualifying orders in before/after periods.",
        "Net revenue formula applied: sum(quantity * unit_price * (1 - COALESCE(discount, 0.0))).",
        "Cancelled orders (order_status = 'cancelled') strictly excluded.",
        "Customer cohort composition remains constant between before and after windows (zero customer drop)."
    ]

    execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return CampaignImpactResponse(
        campaign_id=campaign.campaign_id,
        campaign_name=campaign.name,
        target_region=campaign.region,
        exposed_n=exposed_n,
        control_n=control_n,
        exposed_before=exposed_before,
        exposed_after=exposed_after,
        control_before=control_before,
        control_after=control_after,
        exposed_change=exposed_change,
        control_change=control_change,
        did=did,
        control_standard_error=control_se,
        status=status,
        inference=inference,
        disclaimer="Observational evidence; causation not proven.",
        what_would_change_my_mind=what_would_change_my_mind,
        time_windows={
            "before": {"start": bef_start.strftime("%Y-%m-%d"), "end": bef_end.strftime("%Y-%m-%d")},
            "exposure": {"start": exp_start.strftime("%Y-%m-%d"), "end": exp_end.strftime("%Y-%m-%d")},
            "after": {"start": aft_start.strftime("%Y-%m-%d"), "end": aft_end.strftime("%Y-%m-%d")},
        },
        evidence=evidence_items,
        assumptions=assumptions,
        execution_metadata={
            "execution_time_ms": execution_time_ms,
            "min_sample_size_threshold": min_sample_size,
            "has_sufficient_sample": has_sufficient_sample
        }
    )
