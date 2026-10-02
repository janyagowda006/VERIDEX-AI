"""Initial VERIDEX Database Schema Migration

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-02 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=128), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='ANALYST'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=False)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)

    # 2. Customers Table
    op.create_table(
        'customers',
        sa.Column('customer_id', sa.String(length=32), nullable=False),
        sa.Column('customer_name', sa.String(length=128), nullable=False),
        sa.Column('region', sa.String(length=32), nullable=False),
        sa.Column('customer_segment', sa.String(length=32), nullable=False),
        sa.Column('signup_date', sa.Date(), nullable=False),
        sa.Column('acquisition_channel', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('customer_id')
    )
    op.create_index(op.f('ix_customers_customer_id'), 'customers', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customers_region'), 'customers', ['region'], unique=False)

    # 3. Products Table
    op.create_table(
        'products',
        sa.Column('product_id', sa.String(length=32), nullable=False),
        sa.Column('product_name', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('cost_per_unit', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.PrimaryKeyConstraint('product_id')
    )
    op.create_index(op.f('ix_products_product_id'), 'products', ['product_id'], unique=False)
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)

    # 4. Orders Table
    op.create_table(
        'orders',
        sa.Column('order_id', sa.String(length=32), nullable=False),
        sa.Column('customer_id', sa.String(length=32), nullable=False),
        sa.Column('order_date', sa.Date(), nullable=False),
        sa.Column('sales_channel', sa.String(length=32), nullable=False),
        sa.Column('order_status', sa.String(length=32), nullable=False),
        sa.Column('discount', sa.Numeric(precision=4, scale=2), nullable=False, server_default='0.0'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
        sa.PrimaryKeyConstraint('order_id')
    )
    op.create_index(op.f('ix_orders_order_id'), 'orders', ['order_id'], unique=False)
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_order_date'), 'orders', ['order_date'], unique=False)
    op.create_index(op.f('ix_orders_order_status'), 'orders', ['order_status'], unique=False)

    # 5. Order Items Table
    op.create_table(
        'order_items',
        sa.Column('order_item_id', sa.String(length=32), nullable=False),
        sa.Column('order_id', sa.String(length=32), nullable=False),
        sa.Column('product_id', sa.String(length=32), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.order_id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], ),
        sa.PrimaryKeyConstraint('order_item_id')
    )
    op.create_index(op.f('ix_order_items_order_item_id'), 'order_items', ['order_item_id'], unique=False)
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)

    # 6. Investigations Table
    op.create_table(
        'investigations',
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='IN_PROGRESS'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('turns_used', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tool_calls_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('evidence_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('claims_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('robustness_status', sa.String(length=32), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.user_id'], ),
        sa.PrimaryKeyConstraint('investigation_id')
    )
    op.create_index(op.f('ix_investigations_investigation_id'), 'investigations', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_investigations_status'), 'investigations', ['status'], unique=False)
    op.create_index(op.f('ix_investigations_created_at'), 'investigations', ['created_at'], unique=False)
    op.create_index(op.f('ix_investigations_robustness_status'), 'investigations', ['robustness_status'], unique=False)
    op.create_index(op.f('ix_investigations_owner_id'), 'investigations', ['owner_id'], unique=False)

    # 7. Investigation Reviews Table
    op.create_table(
        'investigation_reviews',
        sa.Column('review_id', sa.String(length=36), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('review_status', sa.String(length=32), nullable=False),
        sa.Column('reviewer_id', sa.String(length=64), nullable=False),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.investigation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('review_id')
    )
    op.create_index(op.f('ix_investigation_reviews_review_id'), 'investigation_reviews', ['review_id'], unique=False)
    op.create_index(op.f('ix_investigation_reviews_investigation_id'), 'investigation_reviews', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_investigation_reviews_review_status'), 'investigation_reviews', ['review_status'], unique=False)
    op.create_index(op.f('ix_investigation_reviews_reviewer_id'), 'investigation_reviews', ['reviewer_id'], unique=False)

    # 8. Investigation Turns Table
    op.create_table(
        'investigation_turns',
        sa.Column('turn_id', sa.String(length=36), nullable=False),
        sa.Column('investigation_id', sa.String(length=36), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('user_question', sa.Text(), nullable=False),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['investigation_id'], ['investigations.investigation_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('turn_id')
    )
    op.create_index(op.f('ix_investigation_turns_turn_id'), 'investigation_turns', ['turn_id'], unique=False)
    op.create_index(op.f('ix_investigation_turns_investigation_id'), 'investigation_turns', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_investigation_turns_turn_number'), 'investigation_turns', ['turn_number'], unique=False)

    # 9. Audit Logs Table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('user_role', sa.String(length=32), nullable=True),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('resource_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='SUCCESS'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('details', sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_role'), 'audit_logs', ['user_role'], unique=False)
    op.create_index(op.f('ix_audit_logs_action_type'), 'audit_logs', ['action_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_id'), 'audit_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_status'), 'audit_logs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('investigation_turns')
    op.drop_table('investigation_reviews')
    op.drop_table('investigations')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('products')
    op.drop_table('customers')
    op.drop_table('users')
