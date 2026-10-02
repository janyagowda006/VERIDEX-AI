import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from sqlalchemy.pool import StaticPool

from app.models.business_data import Base, Customer, Product, Order, OrderItem
from app.services.campaign_impact import (
    campaign_impact,
    CampaignDefinition,
    register_campaign,
    get_campaign,
    CAMPAIGN_REGISTRY
)
from app.schemas.evidence import EvidenceType
from app.main import app


# Isolated in-memory SQLite fixture for campaign tests
@pytest.fixture
def synthetic_campaign_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()

    # Product
    p1 = Product(product_id="PRD-01", product_name="Widget Pro", category="Hardware", unit_price=10.0, cost_per_unit=5.0)
    session.add(p1)

    # 16 Exposed Customers in South
    for i in range(1, 17):
        cid = f"CUST-EXP-{i:02d}"
        session.add(Customer(
            customer_id=cid,
            customer_name=f"Exposed Customer {i}",
            region="South",
            customer_segment="SMB",
            signup_date=date(2024, 1, 1),
            acquisition_channel="Direct"
        ))

    # 16 Control Customers in South
    for i in range(1, 17):
        cid = f"CUST-CTRL-{i:02d}"
        session.add(Customer(
            customer_id=cid,
            customer_name=f"Control Customer {i}",
            region="South",
            customer_segment="Enterprise",
            signup_date=date(2024, 1, 1),
            acquisition_channel="Inbound Web"
        ))

    session.flush()

    # Order Generator Helper
    order_seq = 1
    item_seq = 1

    def create_order(cust_id: str, odate: date, amount: float, status: str = "Completed", discount: float = 0.0):
        nonlocal order_seq, item_seq
        oid = f"ORD-TEST-{order_seq:05d}"
        order_seq += 1
        ord_obj = Order(
            order_id=oid,
            customer_id=cust_id,
            order_date=odate,
            sales_channel="Online",
            order_status=status,
            discount=discount
        )
        session.add(ord_obj)
        # Unit price 10.0, quantity = amount / 10
        qty = int(amount / 10.0)
        session.add(OrderItem(
            order_item_id=f"ITEM-{item_seq:05d}",
            order_id=oid,
            product_id="PRD-01",
            quantity=qty,
            unit_price=10.0
        ))
        item_seq += 1

    # Windows:
    # Before: 2025-04-01 to 2025-06-30
    # Exposure: 2025-07-01 to 2025-09-30
    # After: 2025-10-01 to 2025-12-31

    # 1. Exposed cohort orders
    for i in range(1, 17):
        cid = f"CUST-EXP-{i:02d}"
        # Exposure qualifying order
        create_order(cid, date(2025, 8, 15), 100.0, status="Completed")
        # Before order: 200.0
        create_order(cid, date(2025, 5, 10), 200.0, status="Completed")
        # After order: 350.0
        create_order(cid, date(2025, 11, 20), 350.0, status="Completed")

    # 2. Control cohort orders
    for i in range(1, 17):
        cid = f"CUST-CTRL-{i:02d}"
        # Before order: 100.0
        create_order(cid, date(2025, 5, 15), 100.0, status="Completed")
        # After order: 140.0 for first 8, 160.0 for second 8 (mean = 150.0)
        after_amt = 140.0 if i <= 8 else 160.0
        create_order(cid, date(2025, 11, 10), after_amt, status="Completed")

    # 3. Edge cases: Cancelled orders
    # A) Control customer placed a CANCELLED order during exposure window
    # Must NOT turn them into an exposed customer!
    create_order("CUST-CTRL-01", date(2025, 8, 1), 500.0, status="Cancelled")

    # B) Exposed customer placed a CANCELLED order in before window
    # Must NOT inflate their before revenue!
    create_order("CUST-EXP-01", date(2025, 5, 1), 800.0, status="Cancelled")

    session.commit()
    yield session
    session.close()


@pytest.fixture
def synthetic_campaign_definition():
    return CampaignDefinition(
        campaign_id="TEST-CAMP-DID",
        name="Synthetic Test DiD Campaign",
        region="South",
        exposure_window=(date(2025, 7, 1), date(2025, 9, 30)),
        before_window=(date(2025, 4, 1), date(2025, 6, 30)),
        after_window=(date(2025, 10, 1), date(2025, 12, 31)),
        description="Isolated test fixture campaign"
    )


# -------------------------------------------------------------
# 1. Four Group Averages & Exact DiD Verification
# -------------------------------------------------------------
def test_exact_group_averages_and_did(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )

    # Exposed:
    # Before: each 200.0 -> average = 200.00
    # After: each 350.0 -> average = 350.00
    # Exposed change: 350 - 200 = 150.00
    assert result.exposed_before == 200.00
    assert result.exposed_after == 350.00
    assert result.exposed_change == 150.00

    # Control:
    # Before: each 100.0 -> average = 100.00
    # After: 8*140 + 8*160 = 2400 / 16 = 150.00
    # Control change: 150 - 100 = 50.00
    assert result.control_before == 100.00
    assert result.control_after == 150.00
    assert result.control_change == 50.00

    # DiD = 150.00 - 50.00 = 100.00
    assert result.did == 100.00


# -------------------------------------------------------------
# 2. Sample Counts & Cohort Sizing
# -------------------------------------------------------------
def test_cohort_sample_counts(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    assert result.exposed_n == 16
    assert result.control_n == 16
    assert result.status == "SUCCESS"


# -------------------------------------------------------------
# 3. Cancelled Order Exclusion Verification
# -------------------------------------------------------------
def test_cancelled_orders_excluded(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    # If CUST-CTRL-01's cancelled 500.0 order in exposure was counted,
    # exposed_n would be 17 and control_n would be 15.
    assert result.exposed_n == 16
    assert result.control_n == 16

    # If CUST-EXP-01's cancelled 800.0 order in before window was counted,
    # exposed_before would be (15*200 + 1000) / 16 = 250.0, not 200.0.
    assert result.exposed_before == 200.00


# -------------------------------------------------------------
# 4. Control Group Variability & Standard Error Formula
# -------------------------------------------------------------
def test_control_group_variability(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    # Control diffs: 8 of +40, 8 of +60. Mean = 50.
    # Variance = (8*100 + 8*100)/15 = 1600/15 = 106.6667
    # SD = sqrt(106.6667) = 10.327956
    # SE = 10.327956 / sqrt(16) = 2.581989 -> 2.5820
    assert result.control_standard_error is not None
    assert abs(result.control_standard_error - 2.5820) < 0.005


# -------------------------------------------------------------
# 5. Deterministic Inference Evaluation
# -------------------------------------------------------------
def test_deterministic_inference_supported(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    # did = 100 > 0 and 100 >= 1.96 * 2.582 = 5.06 -> "Supported by evidence"
    assert result.inference == "Supported by evidence"


# -------------------------------------------------------------
# 6. Weak Support Inference when DiD < 1.96 * SE
# -------------------------------------------------------------
def test_deterministic_inference_weak_support(synthetic_campaign_db):
    # Construct a scenario where did > 0 but did < 1.96 * SE
    # e.g., exposed change = 52.00, control change = 50.00, did = 2.00 < 5.06
    # Modify after dates of exposed cohort
    db = synthetic_campaign_db
    # Set exposed after revenue to 252.0 (change = +52.00)
    for i in range(1, 17):
        cid = f"CUST-EXP-{i:02d}"
        ord_obj = db.query(Order).filter(
            Order.customer_id == cid,
            Order.order_date >= date(2025, 10, 1)
        ).first()
        if ord_obj and ord_obj.items:
            ord_obj.items[0].quantity = 25  # 25 * 10 = 250 + 2 for first
            if i <= 8:
                ord_obj.items[0].quantity = 25  # 250
            else:
                ord_obj.items[0].quantity = 25  # 250
    db.commit()

    # Now exposed_after ~ 250.0 -> exposed_change ~ 50.0
    # Let's adjust campaign impact min_sample_size=15
    camp = CampaignDefinition(
        campaign_id="TEST-WEAK",
        name="Weak Support Test",
        region="South",
        exposure_window=(date(2025, 7, 1), date(2025, 9, 30)),
        before_window=(date(2025, 4, 1), date(2025, 6, 30)),
        after_window=(date(2025, 10, 1), date(2025, 12, 31)),
    )
    result = campaign_impact(db, "TEST-WEAK", min_sample_size=15, custom_definition=camp)
    # Exposed change: 250 - 200 = 50.0. Control change: 50.0. did = 0.0 -> "Not supported"
    # If we add small delta so did = 2.0
    first_exp_ord = db.query(Order).filter(
        Order.customer_id == "CUST-EXP-01",
        Order.order_date >= date(2025, 10, 1)
    ).first()
    first_exp_ord.items[0].quantity = 28  # +30.0 total -> avg change +1.875 -> did = 1.88
    db.commit()

    result_weak = campaign_impact(db, "TEST-WEAK", min_sample_size=15, custom_definition=camp)
    assert result_weak.did > 0
    assert result_weak.control_standard_error is not None
    assert result_weak.did < 1.96 * result_weak.control_standard_error
    assert result_weak.inference == "Weak support"


# -------------------------------------------------------------
# 7. Insufficient Data Behavior (N < 15)
# -------------------------------------------------------------
def test_insufficient_sample_size(synthetic_campaign_db, synthetic_campaign_definition):
    # Require N >= 20 when we only have 16 customers
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=20,
        custom_definition=synthetic_campaign_definition
    )
    assert result.status == "INSUFFICIENT_DATA"
    assert result.inference == "Not supported"
    assert result.exposed_n == 16
    assert result.control_n == 16
    # Evidence must still be returned deterministically
    assert len(result.evidence) == 7


# -------------------------------------------------------------
# 8. Exact Mandatory Disclaimer
# -------------------------------------------------------------
def test_exact_disclaimer(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    assert result.disclaimer == "Observational evidence; causation not proven."


# -------------------------------------------------------------
# 9. Evidence Architecture Compliance (DERIVED_FACT & Provenance)
# -------------------------------------------------------------
def test_evidence_architecture(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    assert len(result.evidence) == 7

    for item in result.evidence:
        assert item.evidence_type == EvidenceType.DERIVED_FACT
        assert item.calculation is not None
        assert item.calculation.formula is not None
        assert item.calculation.inputs is not None
        assert item.calculation.output is not None
        assert "Observational evidence; causation not proven." in item.limitations

    # Check specific DiD evidence item
    did_ev = next(e for e in result.evidence if "ev_derived_did" in e.evidence_id)
    assert did_ev.calculation.formula == "exposed_change - control_change"
    assert did_ev.calculation.output == 100.00
    assert did_ev.calculation.inputs["exposed_change"] == 150.00
    assert did_ev.calculation.inputs["control_change"] == 50.00


# -------------------------------------------------------------
# 10. Research Validation Checks ("What Would Change My Mind")
# -------------------------------------------------------------
def test_what_would_change_my_mind_checks(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    assert len(result.what_would_change_my_mind) == 3
    # Verify non-causal phrasing
    for check in result.what_would_change_my_mind:
        assert isinstance(check, str)
        assert len(check) > 10


# -------------------------------------------------------------
# 11. Invalid Campaign Handling
# -------------------------------------------------------------
def test_invalid_campaign_id_rejected(synthetic_campaign_db):
    with pytest.raises(ValueError) as excinfo:
        campaign_impact(
            db=synthetic_campaign_db,
            campaign_id="NON_EXISTENT_CAMPAIGN"
        )
    assert "not found in campaign registry" in str(excinfo.value)


# -------------------------------------------------------------
# 12. Determinism: Repeated Execution Produces Identical Results
# -------------------------------------------------------------
def test_repeated_execution_determinism(synthetic_campaign_db, synthetic_campaign_definition):
    res1 = campaign_impact(synthetic_campaign_db, "TEST-CAMP-DID", 15, synthetic_campaign_definition)
    res2 = campaign_impact(synthetic_campaign_db, "TEST-CAMP-DID", 15, synthetic_campaign_definition)

    assert res1.exposed_before == res2.exposed_before
    assert res1.exposed_after == res2.exposed_after
    assert res1.control_before == res2.control_before
    assert res1.control_after == res2.control_after
    assert res1.did == res2.did
    assert res1.control_standard_error == res2.control_standard_error
    assert res1.inference == res2.inference
    assert res1.status == res2.status


# -------------------------------------------------------------
# 13. Customer with Zero Revenue in One Period Not Dropped
# -------------------------------------------------------------
def test_customer_zero_revenue_preserves_cohort_size(synthetic_campaign_db):
    db = synthetic_campaign_db
    # Delete the before order for CUST-EXP-16
    before_ord = db.query(Order).filter(
        Order.customer_id == "CUST-EXP-16",
        Order.order_date >= date(2025, 4, 1),
        Order.order_date <= date(2025, 6, 30)
    ).first()
    if before_ord:
        db.delete(before_ord)
        db.commit()

    camp = CampaignDefinition(
        campaign_id="TEST-ZERO-REV",
        name="Zero Revenue Test",
        region="South",
        exposure_window=(date(2025, 7, 1), date(2025, 9, 30)),
        before_window=(date(2025, 4, 1), date(2025, 6, 30)),
        after_window=(date(2025, 10, 1), date(2025, 12, 31)),
    )
    result = campaign_impact(db, "TEST-ZERO-REV", 15, camp)
    # CUST-EXP-16 has 0.0 before, but is NOT dropped: cohort N remains 16
    assert result.exposed_n == 16
    # 15 customers with 200.0, 1 customer with 0.0 -> total 3000.0 / 16 = 187.50
    assert result.exposed_before == 187.50


# -------------------------------------------------------------
# 14. API Endpoint Validation (/tools/campaign-impact)
# -------------------------------------------------------------
def test_api_endpoint_tools_campaign_impact(synthetic_campaign_db, synthetic_campaign_definition):
    # Register test campaign in registry for endpoint access
    register_campaign(synthetic_campaign_definition)

    client = TestClient(app)
    from app.core.db import get_db

    def override_get_db():
        try:
            yield synthetic_campaign_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.post(
            "/tools/campaign-impact",
            json={"campaign_id": "TEST-CAMP-DID", "min_sample_size": 15}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == "TEST-CAMP-DID"
        assert data["exposed_n"] == 16
        assert data["control_n"] == 16
        assert data["disclaimer"] == "Observational evidence; causation not proven."
        assert data["status"] == "SUCCESS"
        assert len(data["evidence"]) == 7

        # Invalid campaign returns 400
        err_resp = client.post(
            "/tools/campaign-impact",
            json={"campaign_id": "UNKNOWN_CAMP"}
        )
        assert err_resp.status_code == 400
        assert "not found in campaign registry" in err_resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# -------------------------------------------------------------
# 15. Exactly One Inference Value from Valid Set
# -------------------------------------------------------------
def test_exactly_one_inference_value(synthetic_campaign_db, synthetic_campaign_definition):
    valid_inferences = {"Supported by evidence", "Weak support", "Not supported"}
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    assert result.inference in valid_inferences
    assert isinstance(result.inference, str)


# -------------------------------------------------------------
# 16. No Causal Language Generated by Deterministic Service
# -------------------------------------------------------------
def test_no_causal_claims_in_deterministic_service(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    # The disclaimer must explicitly reject causation
    assert "causation not proven" in result.disclaimer.lower()
    assert result.disclaimer == "Observational evidence; causation not proven."

    # Prohibited causal claims: asserting the campaign caused the change
    prohibited_phrases = ["campaign caused", "proves causality", "causation proven", "proven to cause", "directly caused"]
    all_text = " ".join([
        result.disclaimer,
        result.inference,
        " ".join(result.assumptions),
        " ".join(ev.description for ev in result.evidence),
        " ".join(check for check in result.what_would_change_my_mind)
    ]).lower()

    for phrase in prohibited_phrases:
        assert phrase not in all_text, f"Found prohibited causal phrase '{phrase}' in service output."


# -------------------------------------------------------------
# 17. Selection Bias and Observational Limitations Explicitly Present
# -------------------------------------------------------------
def test_selection_bias_and_observational_limitations(synthetic_campaign_db, synthetic_campaign_definition):
    result = campaign_impact(
        db=synthetic_campaign_db,
        campaign_id="TEST-CAMP-DID",
        min_sample_size=15,
        custom_definition=synthetic_campaign_definition
    )
    # Check limitations in evidence items
    for item in result.evidence:
        assert any("selection bias" in lim.lower() for lim in item.limitations)
        assert any("observational" in lim.lower() for lim in item.limitations)

    # Check assumptions
    assert any("selection bias" in asm.lower() for asm in result.assumptions)
    assert any("observational" in asm.lower() for asm in result.assumptions)


# -------------------------------------------------------------
# 18. Live API Exercise: POST /tools/campaign-impact with CMP-2025-Q3-SOUTH
# -------------------------------------------------------------
def test_api_exercise_demo_campaign(test_db_session):
    client = TestClient(app)
    from app.core.db import get_db

    def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.post(
            "/tools/campaign-impact",
            json={"campaign_id": "CMP-2025-Q3-SOUTH"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == "CMP-2025-Q3-SOUTH"
        assert data["disclaimer"] == "Observational evidence; causation not proven."
        assert "status" in data
        assert "inference" in data
        assert len(data["evidence"]) == 7
        assert len(data["what_would_change_my_mind"]) == 3
        # Test /api/tools/campaign-impact alias
        alias_resp = client.post(
            "/api/tools/campaign-impact",
            json={"campaign_id": "CMP-2025-Q3-SOUTH"}
        )
        assert alias_resp.status_code == 200
        assert alias_resp.json()["campaign_id"] == "CMP-2025-Q3-SOUTH"
    finally:
        app.dependency_overrides.clear()



