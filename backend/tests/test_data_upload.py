import io
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import get_db, Base, engine
from app.services.schema_introspection import get_database_schema
from app.tools.sql_tool import execute_read_only_sql
from app.schemas.sql_tool import SQLQueryRequest


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_upload_csv_success(client, test_db_session):
    """Test uploading a valid CSV dataset."""
    csv_content = "customer_id,region,revenue,profit\n101,North,1500.50,300.00\n102,South,2200.00,450.75\n"
    files = {
        "file": ("test_sales.csv", csv_content.encode("utf-8"), "text/csv")
    }

    response = client.post("/api/data-sources/upload", files=files)
    assert response.status_code in (200, 201)
    data = response.json()

    assert data["status"] == "loaded"
    assert "uploaded_test_sales" in data["table_name"]
    assert data["row_count"] == 2
    assert len(data["columns"]) == 4
    assert set(data["columns"]) == {"customer_id", "region", "revenue", "profit"}

    # Verify queryability via SQL tool
    req = SQLQueryRequest(sql=f"SELECT * FROM {data['table_name']}")
    res = execute_read_only_sql(test_db_session, req)
    assert res.success is True
    assert res.row_count == 2
    assert len(res.data) == 2



def test_upload_excel_success(client, test_db_session):
    """Test uploading a valid Excel (.xlsx) dataset."""
    df = pd.DataFrame({
        "product_id": [1, 2, 3],
        "category": ["Electronics", "Furniture", "Electronics"],
        "price": [299.99, 150.00, 49.99]
    })
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    output.seek(0)

    files = {
        "file": ("test_products.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }

    response = client.post("/api/data-sources/upload", files=files)
    assert response.status_code in (200, 201)
    data = response.json()

    assert data["status"] == "loaded"
    assert "uploaded_test_products" in data["table_name"]
    assert data["row_count"] == 3
    assert len(data["columns"]) == 3
    assert set(data["columns"]) == {"product_id", "category", "price"}


def test_upload_sql_injection_sanitization(client, test_db_session):
    """Test uploading a CSV with unsafe column names and table names to verify SQL injection sanitization."""
    csv_content = "user; DROP TABLE users; --,amount; SELECT 1\n1,100\n2,200\n"
    files = {
        "file": ("malicious; DROP TABLE test; --.csv", csv_content.encode("utf-8"), "text/csv")
    }

    response = client.post("/api/data-sources/upload", files=files)
    assert response.status_code in (200, 201)
    data = response.json()

    table_name = data["table_name"]
    assert "drop_table" in table_name or "malicious" in table_name
    for col in data["columns"]:
        assert ";" not in col
        assert "--" not in col

    # Verify table can be queried safely without SQL error
    req = SQLQueryRequest(sql=f"SELECT * FROM {table_name}")
    res = execute_read_only_sql(test_db_session, req)
    assert res.success is True
    assert res.row_count == 2


def test_upload_unsupported_extension(client):
    """Test uploading an unsupported file format."""
    files = {
        "file": ("script.py", b"print('hello')", "text/plain")
    }

    response = client.post("/api/data-sources/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_upload_malformed_csv(client):
    """Test uploading empty or malformed file."""
    files = {
        "file": ("empty.csv", b"", "text/csv")
    }

    response = client.post("/api/data-sources/upload", files=files)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_schema_introspection_includes_uploaded_table(client, test_db_session):
    """Test that schema introspection dynamically discovers uploaded tables for the AI investigator context."""
    csv_content = "id,name\n1,Alpha\n2,Beta\n"
    files = {
        "file": ("schema_test.csv", csv_content.encode("utf-8"), "text/csv")
    }

    upload_res = client.post("/api/data-sources/upload", files=files)
    assert upload_res.status_code in (200, 201)
    table_name = upload_res.json()["table_name"]

    schema_context = get_database_schema(test_db_session)
    table_names = [t.name for t in schema_context.tables]
    assert table_name in table_names
