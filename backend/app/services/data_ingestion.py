import os
import csv
from datetime import datetime
from typing import List, Tuple
from sqlalchemy.orm import Session
from app.models.business_data import Customer, Product, Order, OrderItem


def validate_csv_data(data_dir: str) -> Tuple[bool, List[str]]:
    """
    Validates CSV data files for schema correctness, integrity, non-nulls, and foreign key references.
    Returns (is_valid, list_of_error_strings).
    """
    errors: List[str] = []

    customers_path = os.path.join(data_dir, "customers.csv")
    products_path = os.path.join(data_dir, "products.csv")
    orders_path = os.path.join(data_dir, "orders.csv")
    order_items_path = os.path.join(data_dir, "order_items.csv")

    for p in [customers_path, products_path, orders_path, order_items_path]:
        if not os.path.exists(p):
            errors.append(f"Missing required CSV file: {p}")
            return False, errors

    # Track IDs for FK & PK validation
    customer_ids = set()
    product_ids = set()
    order_ids = set()
    order_item_ids = set()

    # 1. Validate Customers CSV
    with open(customers_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            cid = row.get("customer_id")
            if not cid:
                errors.append(f"customers.csv L{idx}: Null customer_id")
            elif cid in customer_ids:
                errors.append(f"customers.csv L{idx}: Duplicate customer_id '{cid}'")
            else:
                customer_ids.add(cid)

            if not row.get("region"):
                errors.append(f"customers.csv L{idx}: Null region for customer '{cid}'")

    # 2. Validate Products CSV
    with open(products_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            pid = row.get("product_id")
            if not pid:
                errors.append(f"products.csv L{idx}: Null product_id")
            elif pid in product_ids:
                errors.append(f"products.csv L{idx}: Duplicate product_id '{pid}'")
            else:
                product_ids.add(pid)

            try:
                price = float(row.get("unit_price", -1))
                cost = float(row.get("cost_per_unit", -1))
                if price < 0:
                    errors.append(f"products.csv L{idx}: Negative unit_price for '{pid}'")
                if cost < 0:
                    errors.append(f"products.csv L{idx}: Negative cost_per_unit for '{pid}'")
            except ValueError:
                errors.append(f"products.csv L{idx}: Invalid numeric price/cost for '{pid}'")

    # 3. Validate Orders CSV
    valid_statuses = {"Completed", "Cancelled", "Returned"}
    with open(orders_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            oid = row.get("order_id")
            cid = row.get("customer_id")
            status = row.get("order_status")

            if not oid:
                errors.append(f"orders.csv L{idx}: Null order_id")
            elif oid in order_ids:
                errors.append(f"orders.csv L{idx}: Duplicate order_id '{oid}'")
            else:
                order_ids.add(oid)

            if cid not in customer_ids:
                errors.append(f"orders.csv L{idx}: Invalid customer_id FK '{cid}' for order '{oid}'")

            if status not in valid_statuses:
                errors.append(f"orders.csv L{idx}: Invalid order_status '{status}' for order '{oid}'")

            try:
                discount = float(row.get("discount", 0.0))
                if not (0.0 <= discount <= 1.0):
                    errors.append(f"orders.csv L{idx}: Discount '{discount}' out of range [0, 1]")
            except ValueError:
                errors.append(f"orders.csv L{idx}: Invalid numeric discount for '{oid}'")

    # 4. Validate Order Items CSV
    with open(order_items_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            item_id = row.get("order_item_id")
            oid = row.get("order_id")
            pid = row.get("product_id")

            if not item_id:
                errors.append(f"order_items.csv L{idx}: Null order_item_id")
            elif item_id in order_item_ids:
                errors.append(f"order_items.csv L{idx}: Duplicate order_item_id '{item_id}'")
            else:
                order_item_ids.add(item_id)

            if oid not in order_ids:
                errors.append(f"order_items.csv L{idx}: Invalid order_id FK '{oid}' for item '{item_id}'")

            if pid not in product_ids:
                errors.append(f"order_items.csv L{idx}: Invalid product_id FK '{pid}' for item '{item_id}'")

            try:
                qty = int(row.get("quantity", 0))
                uprice = float(row.get("unit_price", -1))
                if qty <= 0:
                    errors.append(f"order_items.csv L{idx}: Non-positive quantity '{qty}' for item '{item_id}'")
                if uprice < 0:
                    errors.append(f"order_items.csv L{idx}: Negative unit_price for item '{item_id}'")
            except ValueError:
                errors.append(f"order_items.csv L{idx}: Invalid numeric quantity/price for item '{item_id}'")

    is_valid = len(errors) == 0
    return is_valid, errors


def ingest_csv_to_db(data_dir: str, db: Session) -> dict:
    """
    Validates CSV files and loads data into PostgreSQL tables within a single transaction.
    """
    is_valid, errors = validate_csv_data(data_dir)
    if not is_valid:
        raise ValueError(f"CSV Data Validation Failed:\n" + "\n".join(errors[:10]))

    # Clear existing data in reverse dependency order
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Product).delete()
    db.query(Customer).delete()
    db.flush()

    # Load Customers
    cust_count = 0
    with open(os.path.join(data_dir, "customers.csv"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c = Customer(
                customer_id=row["customer_id"],
                customer_name=row["customer_name"],
                region=row["region"],
                customer_segment=row["customer_segment"],
                signup_date=datetime.strptime(row["signup_date"], "%Y-%m-%d").date(),
                acquisition_channel=row["acquisition_channel"]
            )
            db.add(c)
            cust_count += 1

    # Load Products
    prod_count = 0
    with open(os.path.join(data_dir, "products.csv"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            p = Product(
                product_id=row["product_id"],
                product_name=row["product_name"],
                category=row["category"],
                unit_price=float(row["unit_price"]),
                cost_per_unit=float(row["cost_per_unit"])
            )
            db.add(p)
            prod_count += 1

    db.flush()

    # Load Orders
    order_count = 0
    with open(os.path.join(data_dir, "orders.csv"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            o = Order(
                order_id=row["order_id"],
                customer_id=row["customer_id"],
                order_date=datetime.strptime(row["order_date"], "%Y-%m-%d").date(),
                sales_channel=row["sales_channel"],
                order_status=row["order_status"],
                discount=float(row["discount"])
            )
            db.add(o)
            order_count += 1

    db.flush()

    # Load Order Items
    item_count = 0
    with open(os.path.join(data_dir, "order_items.csv"), "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            item = OrderItem(
                order_item_id=row["order_item_id"],
                order_id=row["order_id"],
                product_id=row["product_id"],
                quantity=int(row["quantity"]),
                unit_price=float(row["unit_price"])
            )
            db.add(item)
            item_count += 1

    db.commit()

    return {
        "status": "success",
        "customers_loaded": cust_count,
        "products_loaded": prod_count,
        "orders_loaded": order_count,
        "order_items_loaded": item_count
    }
