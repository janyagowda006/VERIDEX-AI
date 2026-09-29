from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.db import get_db
from app.models.business_data import Customer, Product, Order, OrderItem
from app.services.metrics import calculate_net_revenue
from app.services.schema_introspection import get_database_schema
from app.tools.sql_tool import execute_read_only_sql
from app.schemas.sql_tool import SQLQueryRequest, SQLQueryResult, SchemaContext

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
