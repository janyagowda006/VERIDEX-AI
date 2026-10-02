import math
from datetime import date
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.db import get_db
from app.models.business_data import Base, Customer, Product, Order, OrderItem
from app.schemas.evidence import EvidenceType
from app.services.driver_decomposition import (
    decompose_change,
    ReconciliationError,
    ALLOWED_METRICS,
    DIMENSION_MAPPING
)


@pytest.fixture(scope="function")
def planted_decline_db():
    """
    Dedicated deterministic pytest fixture creating an isolated in-memory SQLite database.
    Does NOT depend on or interact with 'backend/veridex.db'.

    Planted values:
    - Period A: 2025-01-01 to 2025-01-31 (Total Net Revenue: $2,000.00)
    - Period B: 2025-02-01 to 2025-02-28 (Total Net Revenue: $1,000.00)
    - Total Change: -$1,000.00
    - South India is represented:
        * Region 'South India' has Period A: $400.00, Period B: $200.00 (Delta: -$200.00)
    - Karnataka drives exactly 60% of the decline:
        * Region 'Karnataka' has Period A: $1,000.00, Period B: $400.00 (Delta: -$600.00 = 60.0% of decline)
    - Lost group: Region 'Kerala' has Period A: $200.00, Period B: $0.00 (Delta: -$200.00)
    - New group: Region 'Telangana' has Period A: $0.00, Period B: $200.00 (Delta: +$200.00)
    - North India: Region 'North India' has Period A: $400.00, Period B: $200.00 (Delta: -$200.00)
    - Zero/Zero group: Region 'Goa' has Period A: $0.00, Period B: $0.00 (Created via Customer with no orders)
    - Planted Cancelled orders in both periods (MUST be completely excluded).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    # 1. Products
    p_hw = Product(
        product_id="PRD-HW",
        product_name="Server Hardware",
        category="Hardware",
        unit_price=100.00,
        cost_per_unit=50.00
    )
    p_sw = Product(
        product_id="PRD-SW",
        product_name="Analytics License",
        category="Software",
        unit_price=50.00,
        cost_per_unit=20.00
    )
    p_cs = Product(
        product_id="PRD-CS",
        product_name="Cloud VM Instance",
        category="Cloud Services",
        unit_price=25.00,
        cost_per_unit=10.00
    )
    session.add_all([p_hw, p_sw, p_cs])

    # 2. Customers
    c_ka = Customer(
        customer_id="CUST-KA",
        customer_name="Bangalore Enterprises",
        region="Karnataka",
        customer_segment="Enterprise",
        signup_date=date(2024, 1, 1),
        acquisition_channel="Direct"
    )
    c_si = Customer(
        customer_id="CUST-SI",
        customer_name="Chennai Global",
        region="South India",
        customer_segment="Mid-Market",
        signup_date=date(2024, 1, 1),
        acquisition_channel="Inbound Web"
    )
    c_ni = Customer(
        customer_id="CUST-NI",
        customer_name="Delhi Systems",
        region="North India",
        customer_segment="SMB",
        signup_date=date(2024, 1, 1),
        acquisition_channel="Outbound Sales"
    )
    c_lost = Customer(
        customer_id="CUST-LOST",
        customer_name="Kochi Labs",
        region="Kerala",
        customer_segment="SMB",
        signup_date=date(2024, 1, 1),
        acquisition_channel="Direct"
    )
    c_new = Customer(
        customer_id="CUST-NEW",
        customer_name="Hyderabad Infotech",
        region="Telangana",
        customer_segment="Enterprise",
        signup_date=date(2024, 1, 1),
        acquisition_channel="Direct"
    )
    c_zero = Customer(
        customer_id="CUST-ZERO",
        customer_name="Panaji Digital",
        region="Goa",
        customer_segment="SMB",
        signup_date=date(2024, 1, 1),
        acquisition_channel="Direct"
    )
    session.add_all([c_ka, c_si, c_ni, c_lost, c_new, c_zero])

    # 3. Orders & OrderItems for Period A (2025-01-01 to 2025-01-31)
    # Karnataka: $1,000.00 (10 x PRD-HW @ 100)
    o_ka_a = Order(order_id="ORD-KA-A", customer_id="CUST-KA", order_date=date(2025, 1, 10), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_ka_a = OrderItem(order_item_id="ITEM-KA-A", order_id="ORD-KA-A", product_id="PRD-HW", quantity=10, unit_price=100.00)

    # South India: $400.00 (8 x PRD-SW @ 50)
    o_si_a = Order(order_id="ORD-SI-A", customer_id="CUST-SI", order_date=date(2025, 1, 12), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_si_a = OrderItem(order_item_id="ITEM-SI-A", order_id="ORD-SI-A", product_id="PRD-SW", quantity=8, unit_price=50.00)

    # North India: $400.00 (8 x PRD-SW @ 50)
    o_ni_a = Order(order_id="ORD-NI-A", customer_id="CUST-NI", order_date=date(2025, 1, 15), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_ni_a = OrderItem(order_item_id="ITEM-NI-A", order_id="ORD-NI-A", product_id="PRD-SW", quantity=8, unit_price=50.00)

    # Kerala (Lost): $200.00 (8 x PRD-CS @ 25)
    o_lost_a = Order(order_id="ORD-LOST-A", customer_id="CUST-LOST", order_date=date(2025, 1, 20), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_lost_a = OrderItem(order_item_id="ITEM-LOST-A", order_id="ORD-LOST-A", product_id="PRD-CS", quantity=8, unit_price=25.00)

    # Cancelled order in Period A (MUST BE EXCLUDED): $500.00
    o_canc_a = Order(order_id="ORD-CANC-A", customer_id="CUST-KA", order_date=date(2025, 1, 25), sales_channel="Direct", order_status="Cancelled", discount=0.0)
    i_canc_a = OrderItem(order_item_id="ITEM-CANC-A", order_id="ORD-CANC-A", product_id="PRD-HW", quantity=5, unit_price=100.00)

    # 4. Orders & OrderItems for Period B (2025-02-01 to 2025-02-28)
    # Karnataka: $400.00 (4 x PRD-HW @ 100) -> Delta = -$600.00
    o_ka_b = Order(order_id="ORD-KA-B", customer_id="CUST-KA", order_date=date(2025, 2, 10), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_ka_b = OrderItem(order_item_id="ITEM-KA-B", order_id="ORD-KA-B", product_id="PRD-HW", quantity=4, unit_price=100.00)

    # South India: $200.00 (4 x PRD-SW @ 50) -> Delta = -$200.00
    o_si_b = Order(order_id="ORD-SI-B", customer_id="CUST-SI", order_date=date(2025, 2, 12), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_si_b = OrderItem(order_item_id="ITEM-SI-B", order_id="ORD-SI-B", product_id="PRD-SW", quantity=4, unit_price=50.00)

    # North India: $200.00 (4 x PRD-SW @ 50) -> Delta = -$200.00
    o_ni_b = Order(order_id="ORD-NI-B", customer_id="CUST-NI", order_date=date(2025, 2, 15), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_ni_b = OrderItem(order_item_id="ITEM-NI-B", order_id="ORD-NI-B", product_id="PRD-SW", quantity=4, unit_price=50.00)

    # Telangana (New): $200.00 (8 x PRD-CS @ 25) -> Delta = +$200.00
    o_new_b = Order(order_id="ORD-NEW-B", customer_id="CUST-NEW", order_date=date(2025, 2, 20), sales_channel="Direct", order_status="Completed", discount=0.0)
    i_new_b = OrderItem(order_item_id="ITEM-NEW-B", order_id="ORD-NEW-B", product_id="PRD-CS", quantity=8, unit_price=25.00)

    # Cancelled order in Period B (MUST BE EXCLUDED): $800.00
    o_canc_b = Order(order_id="ORD-CANC-B", customer_id="CUST-SI", order_date=date(2025, 2, 25), sales_channel="Direct", order_status="Cancelled", discount=0.0)
    i_canc_b = OrderItem(order_item_id="ITEM-CANC-B", order_id="ORD-CANC-B", product_id="PRD-HW", quantity=8, unit_price=100.00)

    session.add_all([
        o_ka_a, i_ka_a,
        o_si_a, i_si_a,
        o_ni_a, i_ni_a,
        o_lost_a, i_lost_a,
        o_canc_a, i_canc_a,
        o_ka_b, i_ka_b,
        o_si_b, i_si_b,
        o_ni_b, i_ni_b,
        o_new_b, i_new_b,
        o_canc_b, i_canc_b
    ])
    session.commit()

    yield session
    session.close()


# ==============================================================================
# 1. Basic revenue decomposition & simplified standard signature
# ==============================================================================
def test_basic_revenue_decomposition(planted_decline_db):
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region", "category", "segment", "customer"]
    )
    assert res.success is True
    assert res.metric == "revenue"
    assert "region" in res.breakdowns
    assert "category" in res.breakdowns
    assert "segment" in res.breakdowns
    assert "customer" in res.breakdowns
    assert len(res.breakdowns["region"].drivers) > 0


# ==============================================================================
# 2. Total delta correctness
# ==============================================================================
def test_total_delta_correctness(planted_decline_db):
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    assert res.total_revenue_a == 2000.00
    assert res.total_revenue_b == 1000.00
    assert res.total_change == -1000.00
    assert res.percent_change == -50.00


# ==============================================================================
# 3. Contribution reconciliation: each independent dimension reconciles
# ==============================================================================
def test_contribution_reconciliation(planted_decline_db):
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region", "category", "segment", "customer"]
    )
    # Every displayed decomposition level independently reconciles: sum(driver_deltas) == total_change
    for dim_name, breakdown in res.breakdowns.items():
        sum_deltas = sum(d.delta_amount for d in breakdown.drivers)
        assert math.isclose(sum_deltas, res.total_change, abs_tol=1e-2), (
            f"Dimension '{dim_name}' failed invariant: sum({sum_deltas}) != total_change({res.total_change})"
        )
        assert breakdown.reconciled is True


# ==============================================================================
# 4. Karnataka major-driver behavior (South India represented & KA drives exactly 60%)
# ==============================================================================
def test_karnataka_major_driver_behavior(planted_decline_db):
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    drivers_by_label = {d.label: d for d in res.breakdowns["region"].drivers}

    # South India is represented
    assert "South India" in drivers_by_label
    south_india = drivers_by_label["South India"]
    assert south_india.revenue_a == 400.00
    assert south_india.revenue_b == 200.00
    assert south_india.delta_amount == -200.00
    assert south_india.percent_of_total_change == 20.00

    # Karnataka drives exactly 60% of the decline (-600 / -1000 = 60.0%)
    assert "Karnataka" in drivers_by_label
    karnataka = drivers_by_label["Karnataka"]
    assert karnataka.revenue_a == 1000.00
    assert karnataka.revenue_b == 400.00
    assert karnataka.delta_amount == -600.00
    assert math.isclose(karnataka.percent_of_total_change, 60.00, abs_tol=0.01)


# ==============================================================================
# 5. Deterministic Zero-Baseline Semantics: New, Lost, Normal, and Zero/Zero
# ==============================================================================
def test_new_group_percentage_is_null(planted_decline_db):
    """A=0, B>0 -> status=new and percent_change_within_group is null (None)."""
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    drivers_by_label = {d.label: d for d in res.breakdowns["region"].drivers}
    assert "Telangana" in drivers_by_label
    telangana = drivers_by_label["Telangana"]
    assert telangana.status == "new"
    assert telangana.revenue_a == 0.00
    assert telangana.revenue_b == 200.00
    assert telangana.delta_amount == 200.00
    # Growth from zero baseline is undefined: must be null/None, not falsely claiming 100%
    assert telangana.percent_change_within_group is None


def test_lost_group_percentage_is_minus_100(planted_decline_db):
    """A>0, B=0 -> status=lost and percent_change_within_group = -100.0%."""
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    drivers_by_label = {d.label: d for d in res.breakdowns["region"].drivers}
    assert "Kerala" in drivers_by_label
    kerala = drivers_by_label["Kerala"]
    assert kerala.status == "lost"
    assert kerala.revenue_a == 200.00
    assert kerala.revenue_b == 0.00
    assert kerala.delta_amount == -200.00
    assert kerala.percent_change_within_group == -100.00


def test_normal_group_percentage_calculation(planted_decline_db):
    """A>0, B>0 -> status=normal and percent_change_within_group = ((B-A)/A)*100."""
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    drivers_by_label = {d.label: d for d in res.breakdowns["region"].drivers}
    karnataka = drivers_by_label["Karnataka"]
    assert karnataka.status == "normal"
    # ((400 - 1000) / 1000) * 100 = -60.0%
    assert karnataka.percent_change_within_group == -60.00


def test_zero_baseline_period_handling(planted_decline_db):
    """Entire period A has 0 revenue -> overall percent_change is null without division by zero."""
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2024-01-01", "end_date": "2024-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    assert res.total_revenue_a == 0.00
    assert res.total_revenue_b == 1000.00
    assert res.total_change == 1000.00
    assert res.percent_change is None  # Undefined growth from 0 baseline
    for d in res.breakdowns["region"].drivers:
        assert d.percent_change_within_group is None
        assert d.status == "new"


def test_zero_total_change_handling(planted_decline_db):
    """total_change == 0 -> percent_of_total_change = 0.0 without division by zero."""
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        dimensions=["region"]
    )
    assert res.total_change == 0.00
    assert res.percent_change == 0.00
    for d in res.breakdowns["region"].drivers:
        assert d.percent_of_total_change == 0.00
        assert d.delta_amount == 0.00


# ==============================================================================
# 6. Cancelled orders excluded
# ==============================================================================
def test_cancelled_orders_excluded(planted_decline_db):
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    # If cancelled orders were included:
    # Period A would be 2000 + 500 = 2500, Period B = 1000 + 800 = 1800
    assert res.total_revenue_a == 2000.00
    assert res.total_revenue_b == 1000.00
    assert any("cancelled" in a.lower() for a in res.assumptions)
    assert any("cancelled" in lim.lower() for ev in res.evidence for lim in ev.limitations)


# ==============================================================================
# 7. Metric allowlist restriction (strictly 'revenue')
# ==============================================================================
def test_unsupported_metrics_rejected(planted_decline_db):
    """Only 'revenue' is allowed. 'net_revenue', 'profit', 'margin' must be rejected."""
    with pytest.raises(ValueError, match="Unsupported metric"):
        decompose_change(
            db=planted_decline_db,
            metric="net_revenue",
            period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
            dimensions=["region"]
        )

    with pytest.raises(ValueError, match="Unsupported metric"):
        decompose_change(
            db=planted_decline_db,
            metric="profit",
            period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
            dimensions=["region"]
        )


# ==============================================================================
# 8. Dimension allowlist & SQL injection rejection
# ==============================================================================
def test_invalid_dimension_rejected(planted_decline_db):
    with pytest.raises(ValueError, match="Invalid dimension"):
        decompose_change(
            db=planted_decline_db,
            metric="revenue",
            period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
            dimensions=["arbitrary_column"]
        )

    with pytest.raises(ValueError):
        decompose_change(
            db=planted_decline_db,
            metric="revenue",
            period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
            period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
            dimensions=["region; DROP TABLE customers;"]
        )


# ==============================================================================
# 9. Parameterized / Read-Only DB behavior & SQL Injection protection
# ==============================================================================
def test_parameterized_read_only_behavior(planted_decline_db):
    """
    Note on Read-Only Verification:
    - PostgreSQL uses 'SET TRANSACTION READ ONLY' and statement timeouts.
    - SQLite tests verify parameterized bind variables and immutability of tables.
    """
    # Attempt SQL injection via date parameter
    with pytest.raises(ValueError):
        decompose_change(
            db=planted_decline_db,
            metric="revenue",
            period_a={"start_date": "2025-01-01' OR '1'='1", "end_date": "2025-01-31"},
            period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
            dimensions=["region"]
        )

    # Immutability check: Customer table is unchanged
    assert planted_decline_db.query(Customer).count() == 6


# ==============================================================================
# 10. Evidence architecture compatibility
# ==============================================================================
def test_evidence_structure_compliance(planted_decline_db):
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region"]
    )
    assert len(res.evidence) > 0
    for ev in res.evidence:
        assert ev.evidence_type == EvidenceType.DERIVED_FACT
        assert ev.calculation is not None
        assert "delta" in ev.calculation.formula.lower()
        assert "total_delta" in ev.calculation.formula.lower()
        assert ev.calculation.output is not None
        assert len(ev.limitations) > 0
        assert "cancelled" in ev.limitations[0].lower()


# ==============================================================================
# 11. Waterfall reconciliation invariant: sum(values) == total_change
# ==============================================================================
def test_waterfall_reconciliation_and_accumulation(planted_decline_db):
    res = decompose_change(
        db=planted_decline_db,
        metric="revenue",
        period_a={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        period_b={"start_date": "2025-02-01", "end_date": "2025-02-28"},
        dimensions=["region", "category"]
    )
    waterfall = res.waterfall
    assert len(waterfall) > 0

    # Top-level waterfall uses ONLY the primary dimension (region) and does not concatenate dimensions
    region_driver_count = len(res.breakdowns["region"].drivers)
    assert len(waterfall) == region_driver_count

    # Invariant: sum(waterfall[i].value) == total_change
    sum_waterfall_values = sum(item.value for item in waterfall)
    assert math.isclose(sum_waterfall_values, res.total_change, abs_tol=1e-2)

    # Invariant: waterfall[-1].cumulative == total_change
    assert math.isclose(waterfall[-1].cumulative, res.total_change, abs_tol=1e-2)

    # Invariant: running cumulative progression
    running_cum = 0.0
    for item in waterfall:
        running_cum = round(running_cum + item.value, 2)
        assert math.isclose(item.cumulative, running_cum, abs_tol=1e-2)

    # Verify each dimension's breakdown waterfall independently reconciles
    for dim_name, breakdown in res.breakdowns.items():
        assert math.isclose(sum(item.value for item in breakdown.waterfall), res.total_change, abs_tol=1e-2)
        assert math.isclose(breakdown.waterfall[-1].cumulative, res.total_change, abs_tol=1e-2)


# ==============================================================================
# 12. API Endpoint verification (POST /tools/decompose)
# ==============================================================================
def test_api_endpoint_tools_decompose(planted_decline_db):
    def override_get_db():
        try:
            yield planted_decline_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    payload = {
        "metric": "revenue",
        "period_a": {"start_date": "2025-01-01", "end_date": "2025-01-31"},
        "period_b": {"start_date": "2025-02-01", "end_date": "2025-02-28"},
        "dimensions": ["region", "category"]
    }
    response = client.post("/tools/decompose", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_revenue_a"] == 2000.00
    assert data["total_revenue_b"] == 1000.00
    assert data["total_change"] == -1000.00
    assert "region" in data["breakdowns"]
    assert "category" in data["breakdowns"]

    # Invariant assertion via API response
    sum_api_waterfall = sum(item["value"] for item in data["waterfall"])
    assert math.isclose(sum_api_waterfall, data["total_change"], abs_tol=1e-2)
    assert math.isclose(data["waterfall"][-1]["cumulative"], data["total_change"], abs_tol=1e-2)

    # Test /api/tools/decompose alias
    alias_response = client.post("/api/tools/decompose", json=payload)
    assert alias_response.status_code == 200

    # Test unsupported metric returns 400
    bad_metric_payload = dict(payload, metric="net_revenue")
    res_bad_metric = client.post("/tools/decompose", json=bad_metric_payload)
    assert res_bad_metric.status_code == 400

    # Test invalid dimension returns 400
    bad_dim_payload = dict(payload, dimensions=["unsupported_dim"])
    res_bad_dim = client.post("/tools/decompose", json=bad_dim_payload)
    assert res_bad_dim.status_code == 400

    app.dependency_overrides.clear()
