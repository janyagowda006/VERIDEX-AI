from typing import List, Optional, Dict, Any
from app.schemas.sql_tool import SQLQueryResult
from app.schemas.evidence import EvidenceItem, EvidenceType, EvidenceSource


class EvidenceAssembler:
    """
    Deterministic service that transforms verified SQLQueryResult objects into structured EvidenceItem objects (FACT).
    Preserves exact database provenance (SQL text, SHA-256 query hash, timestamp, columns, rows, execution metadata).
    Does NOT execute SQL, call LLM, invent missing data, or generate arbitrary confidence scores.
    """

    def __init__(self):
        self._counter = 0

    def generate_evidence_id(self, prefix: str = "ev_fact") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def extract_fact_evidence(
        self,
        result: SQLQueryResult,
        description: Optional[str] = None,
        max_sample_rows: int = 10
    ) -> Optional[EvidenceItem]:
        """
        Converts a successful SQLQueryResult into a FACT EvidenceItem.
        Returns None if result was unsuccessful or empty without metadata.
        """
        if not result.success or result.data is None:
            return None

        ev_id = self.generate_evidence_id(prefix="ev_fact")
        columns = result.columns or []
        data_rows = result.data or []
        sample_rows = data_rows[:max_sample_rows]

        meta = result.metadata
        query_hash = meta.query_hash if meta else "unknown_hash"
        timestamp = meta.timestamp if meta else ""
        exec_ms = meta.execution_time_ms if meta else 0.0
        truncated = meta.truncated if meta else False

        limitations: List[str] = []
        if truncated:
            limitations.append(f"Result set was truncated to {len(data_rows)} rows limit.")
        if len(data_rows) == 0:
            limitations.append("Query returned zero rows.")

        desc = description or f"Database query returned {result.row_count} row(s) across {len(columns)} column(s)."

        source = EvidenceSource(
            source_type="sql_query",
            query_hash=query_hash,
            sql=result.sql,
            timestamp=timestamp,
            columns=columns,
            relevant_rows=sample_rows,
            execution_metadata={
                "execution_time_ms": exec_ms,
                "row_count": result.row_count,
                "truncated": truncated
            }
        )

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.FACT,
            description=desc,
            source=source,
            calculation=None,
            limitations=limitations
        )
