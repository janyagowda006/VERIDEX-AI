import pytest
from app.models.business_data import Customer, Product, Order, OrderItem
from app.services.metrics import (
    calculate_gross_revenue,
    calculate_net_revenue,
    calculate_order_counts,
    calculate_average_order_value,
    calculate_rates
)


def test_table_record_counts(test_db_session):
    """
    Verifies that expected records are populated into Customer, Product, Order, and OrderItem.
    """
    assert test_db_session.query(Customer).count() == 150
    assert test_db_session.query(Product).count() == 20
    assert test_db_session.query(Order).count() == 1500
    assert test_db_session.query(OrderItem).count() > 3000


def test_foreign_key_relationship(test_db_session):
    """
    Verifies relational navigation: Order -> Customer and Order -> OrderItem -> Product.
    """
    sample_order = test_db_session.query(Order).first()
    assert sample_order is not None
    assert sample_order.customer is not None
    assert sample_order.customer.region in ["North", "South", "East", "West"]
    assert len(sample_order.items) > 0
    assert sample_order.items[0].product is not None


def test_deterministic_metric_calculations(test_db_session):
    """
    Verifies that deterministic metric calculations produce valid positive numeric outputs.
    Does NOT assert hardcoded business conclusions.
    """
    gross_rev = calculate_gross_revenue(test_db_session)
    net_rev = calculate_net_revenue(test_db_session)
    counts = calculate_order_counts(test_db_session)
    aov = calculate_average_order_value(test_db_session)
    rates = calculate_rates(test_db_session)

    assert gross_rev > 0.0
    assert net_rev > 0.0
    assert net_rev <= gross_rev  # Net revenue must be <= Gross revenue due to discounts
    assert counts["total"] == 1500
    assert counts["completed"] + counts["cancelled"] + counts["returned"] == counts["total"]
    assert aov > 0.0
    assert 0.0 <= rates["cancellation_rate"] <= 1.0
    assert 0.0 <= rates["return_rate"] <= 1.0
