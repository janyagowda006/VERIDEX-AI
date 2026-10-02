import sys
import os
import tempfile
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.db import SessionLocal
from scripts.generate_data import generate_synthetic_data
from app.services.data_ingestion import ingest_csv_to_db

db = SessionLocal()
tmp_dir = tempfile.mkdtemp()
print(f"Generating synthetic dataset in temporary directory: {tmp_dir}")
generate_synthetic_data(seed=42, output_dir=tmp_dir)

print("Ingesting synthetic dataset into PostgreSQL database...")
ingest_csv_to_db(tmp_dir, db)

print("\n--- DIRECT POSTGRESQL ROW COUNT VERIFICATION ---")
conn = psycopg2.connect('postgresql://veridex:veridex_pass@localhost:5435/veridex')
cur = conn.cursor()

tables = ['customers', 'products', 'orders', 'order_items', 'users']
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"PostgreSQL Table '{t}': {count} rows")

conn.close()
db.close()
