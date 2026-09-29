import time
import hashlib
import re
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any, List
import sqlglot
import sqlglot.expressions as exp
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas.sql_tool import SQLQueryRequest, SQLQueryResult, QueryMetadata

# Prohibited AST node types for strict read-only enforcement
PROHIBITED_AST_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.TruncateTable,
    exp.AlterTable,
    exp.Command,
)


def validate_sql_safety(raw_sql: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates that a SQL string is syntactically valid and strictly read-only SELECT.
    Returns (is_valid, error_type, error_message).
    """
    cleaned_sql = raw_sql.strip()
    if not cleaned_sql:
        return False, "SYNTAX_ERROR", "Empty SQL query provided."

    # Guard 1: Multi-statement rejection (semicolons separating queries)
    # Strip optional single trailing semicolon
    sql_no_trailing = re.sub(r";\s*$", "", cleaned_sql)
    if ";" in sql_no_trailing:
        return False, "UNSAFE_SQL", "Multi-statement queries separated by semicolons are strictly prohibited."

    # Guard 2: SQLGlot AST Parsing
    try:
        parsed = sqlglot.parse_one(cleaned_sql, read="postgres")
    except sqlglot.errors.ParseError as pe:
        return False, "SYNTAX_ERROR", f"SQL syntax error: {str(pe)}"
    except Exception as e:
        return False, "SYNTAX_ERROR", f"Failed to parse SQL: {str(e)}"

    if parsed is None:
        return False, "SYNTAX_ERROR", "Could not parse SQL query expression."

    # Guard 3: Root expression must be a SELECT
    if not isinstance(parsed, exp.Select):
        return False, "UNSAFE_SQL", f"Only SELECT queries are allowed. Got statement type: '{parsed.key.upper()}'."

    # Guard 4: Recursive AST walk for prohibited modification nodes
    for node in parsed.walk():
        if isinstance(node, PROHIBITED_AST_NODES):
            node_type = node.key.upper() if hasattr(node, "key") else str(type(node))
            return False, "UNSAFE_SQL", f"Prohibited modification operation detected in AST: '{node_type}'."

    return True, None, None


def execute_read_only_sql(db: Session, request: SQLQueryRequest) -> SQLQueryResult:
    """
    Executes a read-only SQL query safely against PostgreSQL (or SQLite dev/test) with statement timeout and result limits.
    """
    raw_sql = request.sql.strip()
    user_limit = request.max_rows or 100
    effective_limit = min(user_limit, 1000)

    # Step 1: Safety validation
    is_valid, error_type, error_msg = validate_sql_safety(raw_sql)
    if not is_valid:
        return SQLQueryResult(
            success=False,
            sql=raw_sql,
            error_type=error_type,
            error_message=error_msg
        )

    # Step 2: Determine SQLGlot target dialect from DB bind
    dialect_name = db.bind.dialect.name if hasattr(db, "bind") and db.bind else "postgres"
    sqlglot_dialect = "sqlite" if dialect_name == "sqlite" else "postgres"

    # Apply LIMIT injection safely via SQLGlot
    try:
        parsed = sqlglot.parse_one(re.sub(r";\s*$", "", raw_sql), read="postgres")
        if not parsed.args.get("limit"):
            parsed = parsed.limit(effective_limit + 1)
        sql_to_execute = parsed.sql(dialect=sqlglot_dialect)
    except Exception:
        sql_no_semi = re.sub(r";\s*$", "", raw_sql)
        sql_to_execute = f"SELECT * FROM ({sql_no_semi}) AS __wrap_query LIMIT {effective_limit + 1}"

    start_time = time.perf_counter()
    query_timestamp = datetime.now(timezone.utc).isoformat()
    query_hash = hashlib.sha256(raw_sql.encode("utf-8")).hexdigest()

    try:
        # Step 3: Execution under read-only transaction and statement timeout (if PostgreSQL)
        if dialect_name in ["postgres", "postgresql"]:
            db.execute(text("SET LOCAL statement_timeout = '3000ms'"))
            db.execute(text("SET TRANSACTION READ ONLY"))

        result = db.execute(text(sql_to_execute))
        columns = list(result.keys()) if result.returns_rows else []
        rows_fetched = result.fetchall() if result.returns_rows else []

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Check truncation
        truncated = len(rows_fetched) > effective_limit
        final_rows = rows_fetched[:effective_limit]

        # Convert rows to dicts
        data_dicts: List[Dict[str, Any]] = []
        for r in final_rows:
            row_dict = {}
            for col_name, val in zip(columns, r):
                if hasattr(val, "isoformat"):
                    row_dict[col_name] = val.isoformat()
                elif hasattr(val, "__float__"):
                    row_dict[col_name] = float(val)
                else:
                    row_dict[col_name] = val
            data_dicts.append(row_dict)

        metadata = QueryMetadata(
            execution_time_ms=execution_time_ms,
            row_count=len(data_dicts),
            columns=columns,
            truncated=truncated,
            query_hash=query_hash,
            timestamp=query_timestamp
        )

        return SQLQueryResult(
            success=True,
            sql=raw_sql,
            data=data_dicts,
            columns=columns,
            row_count=len(data_dicts),
            metadata=metadata
        )

    except Exception as e:
        err_str = str(e)
        if "canceling statement due to statement timeout" in err_str.lower() or "timeout" in err_str.lower():
            err_type = "TIMEOUT"
            err_msg = "Query execution cancelled: exceeded 3.0 second statement timeout limit."
        elif "does not exist" in err_str.lower() or "no such table" in err_str.lower() or "no such column" in err_str.lower() or "column" in err_str.lower():
            err_type = "UNKNOWN_IDENTIFIER"
            err_msg = f"Database execution error: {err_str.splitlines()[0]}"
        else:
            err_type = "EXECUTION_ERROR"
            err_msg = f"Database execution error: {err_str.splitlines()[0]}"

        return SQLQueryResult(
            success=False,
            sql=raw_sql,
            error_type=err_type,
            error_message=err_msg
        )
