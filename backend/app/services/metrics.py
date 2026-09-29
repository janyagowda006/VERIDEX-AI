from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.business_data import Order, OrderItem


def calculate_gross_revenue(db: Session) -> float:
    """
    Calculates total Gross Revenue = sum(quantity * unit_price) for Completed orders.
    """
    query = (
        db.query(func.sum(OrderItem.quantity * OrderItem.unit_price))
        .join(Order, OrderItem.order_id == Order.order_id)
        .filter(Order.order_status == "Completed")
    )
    result = query.scalar()
    return float(result) if result is not None else 0.0


def calculate_net_revenue(db: Session) -> float:
    """
    Calculates total Net Revenue = sum(quantity * unit_price * (1 - discount)) for Completed orders.
    """
    query = (
        db.query(func.sum(OrderItem.quantity * OrderItem.unit_price * (1 - Order.discount)))
        .join(Order, OrderItem.order_id == Order.order_id)
        .filter(Order.order_status == "Completed")
    )
    result = query.scalar()
    return float(result) if result is not None else 0.0


def calculate_order_counts(db: Session) -> dict:
    """
    Calculates total, completed, cancelled, and returned order counts.
    """
    total = db.query(func.count(Order.order_id)).scalar() or 0
    completed = db.query(func.count(Order.order_id)).filter(Order.order_status == "Completed").scalar() or 0
    cancelled = db.query(func.count(Order.order_id)).filter(Order.order_status == "Cancelled").scalar() or 0
    returned = db.query(func.count(Order.order_id)).filter(Order.order_status == "Returned").scalar() or 0

    return {
        "total": total,
        "completed": completed,
        "cancelled": cancelled,
        "returned": returned
    }


def calculate_average_order_value(db: Session) -> float:
    """
    Calculates Average Order Value (AOV) = Net Revenue / Completed Order Count.
    """
    net_rev = calculate_net_revenue(db)
    counts = calculate_order_counts(db)
    if counts["completed"] == 0:
        return 0.0
    return round(net_rev / counts["completed"], 2)


def calculate_rates(db: Session) -> dict:
    """
    Calculates cancellation rate and return rate over total orders.
    """
    counts = calculate_order_counts(db)
    total = counts["total"]
    if total == 0:
        return {"cancellation_rate": 0.0, "return_rate": 0.0}

    return {
        "cancellation_rate": round(counts["cancelled"] / total, 4),
        "return_rate": round(counts["returned"] / total, 4)
    }
