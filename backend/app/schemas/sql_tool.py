from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class SQLQueryRequest(BaseModel):
    """
    Request model for executing a read-only SQL query.
    """
    sql: str = Field(..., description="The SQL SELECT query string to execute safely.")
    max_rows: Optional[int] = Field(default=100, ge=1, le=1000, description="Maximum number of rows to return.")


class QueryMetadata(BaseModel):
    """
    Deterministic metadata payload generated for evidence assembler compatibility.
    """
    execution_time_ms: float
    row_count: int
    columns: List[str]
    truncated: bool
    query_hash: str
    timestamp: str


class SQLQueryResult(BaseModel):
    """
    Structured result returned by the SQL investigation tool.
    """
    success: bool
    sql: str
    data: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: int = 0
    metadata: Optional[QueryMetadata] = None
    error_type: Optional[str] = None  # e.g., "UNSAFE_SQL", "SYNTAX_ERROR", "TIMEOUT", "EXECUTION_ERROR", "UNKNOWN_IDENTIFIER"
    error_message: Optional[str] = None


class ForeignKeySchema(BaseModel):
    constrained_columns: List[str]
    referred_table: str
    referred_columns: List[str]


class ColumnSchema(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class TableSchema(BaseModel):
    name: str
    columns: List[ColumnSchema]
    foreign_keys: List[ForeignKeySchema] = []


class SchemaContext(BaseModel):
    """
    Deterministic context model representing the database schema for future agent context.
    """
    tables: List[TableSchema]
