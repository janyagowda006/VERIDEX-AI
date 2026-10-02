from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.schemas.sql_tool import SchemaContext, TableSchema, ColumnSchema, ForeignKeySchema

EXCLUDED_SYSTEM_TABLES = {
    "users",
    "investigations",
    "investigation_turns",
    "investigation_reviews",
    "audit_logs",
    "alembic_version"
}


def get_database_schema(db: Session) -> SchemaContext:
    """
    Deterministically introspects database tables, columns, data types, primary keys,
    and foreign keys for AI agent context. Supports dynamic uploaded dataset tables.
    """
    bind = db.get_bind()
    inspector = inspect(bind)
    tables: list[TableSchema] = []

    try:
        all_table_names = inspector.get_table_names()
    except Exception:
        all_table_names = ["customers", "products", "orders", "order_items"]

    # Filter out system/internal tables
    target_tables = [t for t in all_table_names if t.lower() not in EXCLUDED_SYSTEM_TABLES]

    # Always ensure core business tables appear first if present
    core_tables = ["customers", "products", "orders", "order_items"]
    ordered_tables = [t for t in core_tables if t in target_tables]
    ordered_tables.extend([t for t in target_tables if t not in core_tables])

    for table_name in ordered_tables:
        if not inspector.has_table(table_name):
            continue

        columns_info = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pk_cols = set(pk_constraint.get("constrained_columns", []))
        fk_constraints = inspector.get_foreign_keys(table_name)

        col_schemas: list[ColumnSchema] = []
        for col in columns_info:
            cname = col["name"]
            col_type = str(col["type"])
            is_nullable = bool(col.get("nullable", True))
            is_pk = cname in pk_cols

            col_schemas.append(ColumnSchema(
                name=cname,
                type=col_type,
                nullable=is_nullable,
                primary_key=is_pk
            ))

        fk_schemas: list[ForeignKeySchema] = []
        for fk in fk_constraints:
            fk_schemas.append(ForeignKeySchema(
                constrained_columns=fk.get("constrained_columns", []),
                referred_table=fk.get("referred_table", ""),
                referred_columns=fk.get("referred_columns", [])
            ))

        tables.append(TableSchema(
            name=table_name,
            columns=col_schemas,
            foreign_keys=fk_schemas
        ))

    return SchemaContext(tables=tables)
