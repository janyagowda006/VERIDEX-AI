import pytest
from app.schemas.sql_tool import SQLQueryRequest
from app.tools.sql_tool import validate_sql_safety, execute_read_only_sql
from app.services.schema_introspection import get_database_schema


def test_validate_sql_safety_valid():
    """
    Verifies valid SELECT statements pass safety validation.
    """
    valid, err_type, err_msg = validate_sql_safety("SELECT * FROM customers WHERE region = 'North'")
    assert valid is True
    assert err_type is None
    assert err_msg is None


def test_validate_sql_safety_syntax_error():
    """
    Verifies malformed SQL syntax returns SYNTAX_ERROR.
    """
    valid, err_type, err_msg = validate_sql_safety("SELECT FROM WHERE customers")
    assert valid is False
    assert err_type == "SYNTAX_ERROR"
    assert "syntax error" in err_msg.lower() or "parse" in err_msg.lower()


def test_validate_sql_safety_rejections():
    """
    Verifies INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, and multi-statements return UNSAFE_SQL.
    """
    unauthorized_queries = [
        "INSERT INTO customers (customer_id, customer_name) VALUES ('C1', 'Hack')",
        "UPDATE orders SET discount = 0.5 WHERE order_id = 'ORD-00001'",
        "DELETE FROM products WHERE product_id = 'PRD-101'",
        "DROP TABLE customers",
        "ALTER TABLE orders ADD COLUMN hack TEXT",
        "TRUNCATE TABLE order_items",
        "SELECT * FROM customers; DROP TABLE orders;"
    ]

    for q in unauthorized_queries:
        valid, err_type, err_msg = validate_sql_safety(q)
        assert valid is False, f"Query '{q}' should have been rejected as UNSAFE_SQL"
        assert err_type == "UNSAFE_SQL"


def test_execute_read_only_sql_select(test_db_session):
    """
    Verifies execution of a valid SELECT query against the test database.
    """
    req = SQLQueryRequest(sql="SELECT customer_id, customer_name, region FROM customers ORDER BY customer_id LIMIT 5")
    res = execute_read_only_sql(test_db_session, req)

    assert res.success is True
    assert res.row_count == 5
    assert len(res.data) == 5
    assert res.columns == ["customer_id", "customer_name", "region"]
    assert res.metadata is not None
    assert res.metadata.truncated is False
    assert res.metadata.query_hash is not None


def test_execute_read_only_sql_aggregation(test_db_session):
    """
    Verifies execution of an aggregation query (COUNT, GROUP BY).
    """
    req = SQLQueryRequest(sql="SELECT region, COUNT(customer_id) AS total_cust FROM customers GROUP BY region")
    res = execute_read_only_sql(test_db_session, req)

    assert res.success is True
    assert res.row_count == 4  # 4 regions
    assert "region" in res.columns
    assert "total_cust" in res.columns


def test_execute_read_only_sql_relational_join(test_db_session):
    """
    Verifies execution of a 4-table relational JOIN query deriving order region from customers.
    """
    sql = """
    SELECT
        c.region,
        p.category,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(oi.quantity * oi.unit_price) AS total_revenue
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE o.order_status = 'Completed'
    GROUP BY c.region, p.category
    ORDER BY total_revenue DESC
    """
    req = SQLQueryRequest(sql=sql, max_rows=50)
    res = execute_read_only_sql(test_db_session, req)

    assert res.success is True
    assert res.row_count > 0
    assert "region" in res.columns
    assert "category" in res.columns
    assert "total_orders" in res.columns
    assert "total_revenue" in res.columns


def test_execute_read_only_sql_limit_enforcement(test_db_session):
    """
    Verifies that requests returning more rows than max_rows are truncated and flagged appropriately.
    """
    req = SQLQueryRequest(sql="SELECT * FROM orders", max_rows=10)
    res = execute_read_only_sql(test_db_session, req)

    assert res.success is True
    assert res.row_count == 10
    assert len(res.data) == 10
    assert res.metadata.truncated is True


def test_execute_read_only_sql_unknown_identifier(test_db_session):
    """
    Verifies execution of a query referencing a non-existent table returns UNKNOWN_IDENTIFIER error.
    """
    req = SQLQueryRequest(sql="SELECT * FROM non_existent_table")
    res = execute_read_only_sql(test_db_session, req)

    assert res.success is False
    assert res.error_type == "UNKNOWN_IDENTIFIER"
    assert "non_existent_table" in res.error_message.lower() or "error" in res.error_message.lower()


def test_schema_introspection(test_db_session):
    """
    Verifies get_database_schema returns accurate table names, columns, primary keys, and foreign keys.
    """
    schema = get_database_schema(test_db_session)
    table_names = [t.name for t in schema.tables]

    assert "customers" in table_names
    assert "products" in table_names
    assert "orders" in table_names
    assert "order_items" in table_names

    # Check customers table schema
    cust_table = next(t for t in schema.tables if t.name == "customers")
    cust_cols = [c.name for c in cust_table.columns]
    assert "customer_id" in cust_cols
    assert "region" in cust_cols
    assert "customer_segment" in cust_cols

    # Check orders table schema (confirming region is NOT in orders table)
    orders_table = next(t for t in schema.tables if t.name == "orders")
    orders_cols = [c.name for c in orders_table.columns]
    assert "order_id" in orders_cols
    assert "customer_id" in orders_cols
    assert "region" not in orders_cols  # Single Source of Truth rule!
