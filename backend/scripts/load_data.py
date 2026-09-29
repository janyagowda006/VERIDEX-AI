import os
import sys

backend_dir = os.path.dirname(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.business_data import Base
from app.services.data_ingestion import ingest_csv_to_db
from scripts.generate_data import generate_synthetic_data

DATA_DIR = os.path.join(os.path.dirname(backend_dir), "data")


def main():
    print("[LOAD DATA] Checking synthetic CSV files in 'data/'...")
    required_files = ["customers.csv", "products.csv", "orders.csv", "order_items.csv"]
    missing = [f for f in required_files if not os.path.exists(os.path.join(DATA_DIR, f))]

    if missing:
        print(f"[LOAD DATA] Missing files {missing}. Generating synthetic dataset...")
        generate_synthetic_data(seed=42, output_dir=DATA_DIR)
    else:
        print("[LOAD DATA] Found existing CSV files.")

    db_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    print(f"[LOAD DATA] Connecting to database...")

    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        Base.metadata.create_all(bind=engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = TestingSessionLocal()

        print("[LOAD DATA] Validating CSVs and ingesting into database...")
        result = ingest_csv_to_db(DATA_DIR, db)
        print("[LOAD DATA] Ingestion successful!")
        print(f"  - Customers: {result['customers_loaded']}")
        print(f"  - Products: {result['products_loaded']}")
        print(f"  - Orders: {result['orders_loaded']}")
        print(f"  - Order Items: {result['order_items_loaded']}")
        db.close()
    except Exception as e:
        print(f"[LOAD DATA NOTICE] PostgreSQL container not running or connection failed: {e}")
        print("[LOAD DATA NOTICE] Falling back to SQLite local database for offline verification...")
        sqlite_url = f"sqlite:///{os.path.join(DATA_DIR, 'veridex_dev.db')}"
        engine = create_engine(sqlite_url)

        # Enable SQLite foreign key constraints
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(bind=engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = TestingSessionLocal()

        result = ingest_csv_to_db(DATA_DIR, db)
        print(f"[LOAD DATA] SQLite Offline Ingestion successful ('{sqlite_url}')!")
        print(f"  - Customers: {result['customers_loaded']}")
        print(f"  - Products: {result['products_loaded']}")
        print(f"  - Orders: {result['orders_loaded']}")
        print(f"  - Order Items: {result['order_items_loaded']}")
        db.close()


if __name__ == "__main__":
    main()
