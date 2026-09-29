import os
import csv
import random
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def generate_synthetic_data(seed: int = 42, output_dir: str = DATA_DIR):
    """
    Generates realistic, reproducible synthetic business dataset.
    Uses fixed random seed for 100% deterministic reproducibility.
    """
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    # 1. Generate Products (20 products across 4 categories)
    categories = ["Hardware", "Software", "Cloud Services", "Support"]
    product_templates = [
        ("Enterprise Server X1", "Hardware", 2500.00, 1500.00),
        ("Workstation Pro 15", "Hardware", 1200.00, 750.00),
        ("Cloud Router 5G", "Hardware", 450.00, 250.00),
        ("Backup Unit 4TB", "Hardware", 300.00, 160.00),
        ("Edge Gateway", "Hardware", 650.00, 380.00),
        ("Analytics Suite License", "Software", 800.00, 100.00),
        ("Security Shield Pro", "Software", 400.00, 50.00),
        ("Database Manager", "Software", 1500.00, 200.00),
        ("DevOps Toolchain", "Software", 600.00, 80.00),
        ("AI Inference Engine", "Software", 2000.00, 300.00),
        ("Cloud Compute Instance / hr", "Cloud Services", 150.00, 60.00),
        ("Cloud Storage Tier 1", "Cloud Services", 80.00, 25.00),
        ("Managed Kubernetes Pool", "Cloud Services", 500.00, 200.00),
        ("Serverless Gateway", "Cloud Services", 120.00, 40.00),
        ("CDN Traffic Bandwidth", "Cloud Services", 220.00, 90.00),
        ("24/7 Enterprise Support", "Support", 1000.00, 400.00),
        ("Standard SLA Support", "Support", 350.00, 120.00),
        ("Onboarding Package", "Support", 1200.00, 500.00),
        ("Architecture Audit", "Support", 2500.00, 1000.00),
        ("Custom Integration Consulting", "Support", 3000.00, 1200.00),
    ]

    products = []
    for i, (pname, cat, price, cost) in enumerate(product_templates, start=101):
        products.append({
            "product_id": f"PRD-{i}",
            "product_name": pname,
            "category": cat,
            "unit_price": f"{price:.2f}",
            "cost_per_unit": f"{cost:.2f}"
        })

    # Write products.csv
    products_file = os.path.join(output_dir, "products.csv")
    with open(products_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["product_id", "product_name", "category", "unit_price", "cost_per_unit"])
        writer.writeheader()
        writer.writerows(products)

    # 2. Generate Customers (150 customers across 4 regions and 3 segments)
    regions = ["North", "South", "East", "West"]
    segments = ["Enterprise", "Mid-Market", "SMB"]
    channels = ["Direct", "Inbound Web", "Partner Referral", "Outbound Sales"]

    first_names = ["Apex", "Nexus", "Vertex", "Quantum", "Starlight", "Horizon", "Pinnacle", "Vanguard", "Synergy", "Beacon",
                   "Omega", "Alpha", "Zenith", "Solaris", "Titan", "Velocity", "Crestview", "Summit", "Matrix", "Echo"]
    last_names = ["Technologies", "Solutions", "Global", "Systems", "Corp", "Industries", "Logistics", "Digital", "Data", "Labs"]

    customers = []
    start_signup = datetime(2024, 1, 1)

    for i in range(1, 151):
        cid = f"CUST-{i:04d}"
        cname = f"{random.choice(first_names)} {random.choice(last_names)} {i}"
        reg = random.choice(regions)
        seg = random.choices(segments, weights=[0.2, 0.35, 0.45])[0]
        days_offset = random.randint(0, 365)
        signup_dt = (start_signup + timedelta(days=days_offset)).strftime("%Y-%m-%d")
        acq_chan = random.choice(channels)

        customers.append({
            "customer_id": cid,
            "customer_name": cname,
            "region": reg,
            "customer_segment": seg,
            "signup_date": signup_dt,
            "acquisition_channel": acq_chan
        })

    # Write customers.csv
    customers_file = os.path.join(output_dir, "customers.csv")
    with open(customers_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["customer_id", "customer_name", "region", "customer_segment", "signup_date", "acquisition_channel"])
        writer.writeheader()
        writer.writerows(customers)

    # 3. Generate Orders & Order Items (1500 orders across 12 months)
    # Notice: orders does NOT contain a region column! Region is derived from customers.
    sales_channels = ["Online", "Retail", "Partner"]
    order_statuses = ["Completed", "Cancelled", "Returned"]

    start_date = datetime(2025, 1, 1)
    orders = []
    order_items = []
    item_counter = 10001

    for oidx in range(1, 1501):
        oid = f"ORD-{oidx:05d}"
        cust = random.choice(customers)
        cid = cust["customer_id"]

        # Date distribution across 2025
        days_offset = random.randint(0, 360)
        odate = start_date + timedelta(days=days_offset)
        odate_str = odate.strftime("%Y-%m-%d")

        schan = random.choice(sales_channels)

        # Status weighting: ~82% Completed, ~12% Cancelled, ~6% Returned
        # Q3 regional pattern introduced naturally via order status weights for South region in Q3
        is_q3 = 7 <= odate.month <= 9
        if cust["region"] == "South" and is_q3:
            status = random.choices(order_statuses, weights=[0.60, 0.30, 0.10])[0]
        else:
            status = random.choices(order_statuses, weights=[0.85, 0.10, 0.05])[0]

        # Discount range: 0% to 25%
        discount = round(random.choice([0.0, 0.05, 0.10, 0.15, 0.20, 0.25]), 2)

        orders.append({
            "order_id": oid,
            "customer_id": cid,
            "order_date": odate_str,
            "sales_channel": schan,
            "order_status": status,
            "discount": f"{discount:.2f}"
        })

        # Generate 1 to 4 order items per order
        num_items = random.randint(1, 4)
        selected_products = random.sample(products, num_items)

        for p in selected_products:
            item_id = f"ITEM-{item_counter}"
            item_counter += 1
            qty = random.randint(1, 10)
            uprice = float(p["unit_price"])

            order_items.append({
                "order_item_id": item_id,
                "order_id": oid,
                "product_id": p["product_id"],
                "quantity": qty,
                "unit_price": f"{uprice:.2f}"
            })

    # Write orders.csv
    orders_file = os.path.join(output_dir, "orders.csv")
    with open(orders_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["order_id", "customer_id", "order_date", "sales_channel", "order_status", "discount"])
        writer.writeheader()
        writer.writerows(orders)

    # Write order_items.csv
    order_items_file = os.path.join(output_dir, "order_items.csv")
    with open(order_items_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["order_item_id", "order_id", "product_id", "quantity", "unit_price"])
        writer.writeheader()
        writer.writerows(order_items)

    print(f"[DATA GENERATOR] Successfully generated synthetic dataset in '{output_dir}':")
    print(f"  - Products: {len(products)}")
    print(f"  - Customers: {len(customers)}")
    print(f"  - Orders: {len(orders)}")
    print(f"  - Order Items: {len(order_items)}")


if __name__ == "__main__":
    generate_synthetic_data()
