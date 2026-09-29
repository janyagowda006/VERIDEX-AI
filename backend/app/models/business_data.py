from sqlalchemy import Column, String, Numeric, Integer, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String(32), primary_key=True, index=True)
    customer_name = Column(String(128), nullable=False)
    region = Column(String(32), nullable=False, index=True)
    customer_segment = Column(String(32), nullable=False)
    signup_date = Column(Date, nullable=False)
    acquisition_channel = Column(String(64), nullable=False)

    orders = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(32), primary_key=True, index=True)
    product_name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False, index=True)
    unit_price = Column(Numeric(10, 2), nullable=False)
    cost_per_unit = Column(Numeric(10, 2), nullable=False)

    order_items = relationship("OrderItem", back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(32), primary_key=True, index=True)
    customer_id = Column(String(32), ForeignKey("customers.customer_id"), nullable=False, index=True)
    order_date = Column(Date, nullable=False, index=True)
    sales_channel = Column(String(32), nullable=False)
    order_status = Column(String(32), nullable=False, index=True)
    discount = Column(Numeric(4, 2), nullable=False, default=0.0)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = Column(String(32), primary_key=True, index=True)
    order_id = Column(String(32), ForeignKey("orders.order_id"), nullable=False, index=True)
    product_id = Column(String(32), ForeignKey("products.product_id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
