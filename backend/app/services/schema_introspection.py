from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.schemas.sql_tool import SchemaContext, TableSchema, ColumnSchema, ForeignKeySchema
from app.models.business_data import Base


def get_database_schema(db: Session) -> SchemaContext:
    """
    Deterministically introspects database tables, columns, data types, primary keys,
    and foreign keys for future AI agent context.
    """
    bind = db.get_bind()
    inspector = inspect(bind)
    tables: list[TableSchema] = []

    # Introspect target tables defined in Base metadata
    target_tables = ["customers", "products", "orders", "order_items"]

    for table_name in target_tables:
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
