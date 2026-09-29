import os
import tempfile
import pytest
from scripts.generate_data import generate_synthetic_data
from app.services.data_ingestion import validate_csv_data


def test_data_generation_reproducibility():
    """
    Verifies that calling generate_synthetic_data with seed=42 reproducibly generates matching CSV files.
    """
    with tempfile.TemporaryDirectory() as dir1, tempfile.TemporaryDirectory() as dir2:
        generate_synthetic_data(seed=42, output_dir=dir1)
        generate_synthetic_data(seed=42, output_dir=dir2)

        for filename in ["customers.csv", "products.csv", "orders.csv", "order_items.csv"]:
            p1 = os.path.join(dir1, filename)
            p2 = os.path.join(dir2, filename)
            with open(p1, "r", encoding="utf-8") as f1, open(p2, "r", encoding="utf-8") as f2:
                assert f1.read() == f2.read(), f"File content mismatch for {filename}"


def test_csv_validation_valid():
    """
    Verifies that valid generated CSV data passes all 12 validation rules.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        generate_synthetic_data(seed=42, output_dir=tmp_dir)
        is_valid, errors = validate_csv_data(tmp_dir)
        assert is_valid is True, f"Expected valid CSVs, got errors: {errors}"
        assert len(errors) == 0
