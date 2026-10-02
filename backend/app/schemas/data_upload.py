from pydantic import BaseModel
from typing import List, Optional


class DataSourceUploadResponse(BaseModel):
    """
    Response schema for dynamic dataset file upload (CSV / Excel).
    """
    dataset_id: str
    filename: str
    format: str
    table_name: str
    columns: List[str]
    row_count: int
    status: str = "loaded"
    message: Optional[str] = None
