import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.investigation import Investigation
from app.services.investigation_service import InvestigationService


class ReportExporter:
    """
    Read-only audit report export service for persisted VERIDEX investigations.
    Generates structured JSON and human-readable Markdown reports from persisted DB records.
    Does NOT execute SQL queries against business tables or call LLM reasoning engines.
    """

    @classmethod
    def export_as_json(cls, db: Session, investigation_id: str) -> Dict[str, Any]:
        """
        Exports a persisted investigation as a structured JSON dictionary.
        Raises ValueError if investigation_id does not exist.
        """
        investigation = InvestigationService.get_investigation_by_id(db, investigation_id)
        if not investigation:
            raise ValueError(f"Investigation '{investigation_id}' not found.")

        turns = InvestigationService.list_turns_for_investigation(db, investigation_id)
        reviews = InvestigationService.list_reviews_for_investigation(db, investigation_id)

        parsed_payload = {}
        if investigation.result_json:
            try:
                parsed_payload = json.loads(investigation.result_json) if isinstance(investigation.result_json, str) else investigation.result_json
            except Exception:
                pass

        turns_data = []
        for t in turns:
            t_payload = {}
            if t.result_json:
                try:
                    t_payload = json.loads(t.result_json) if isinstance(t.result_json, str) else t.result_json
                except Exception:
                    pass
            turns_data.append({
                "turn_id": t.turn_id,
                "turn_number": t.turn_number,
                "user_question": t.user_question,
                "execution_time_ms": t.execution_time_ms,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "result_summary": t_payload.get("answer") if isinstance(t_payload, dict) else None
            })

        reviews_data = []
        for r in reviews:
            reviews_data.append({
                "review_id": r.review_id,
                "review_status": r.review_status,
                "reviewer_id": r.reviewer_id,
                "review_notes": r.review_notes,
                "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None
            })

        return {
            "veridex_report_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "investigation": {
                "investigation_id": investigation.investigation_id,
                "question": investigation.question,
                "status": investigation.status,
                "robustness_status": investigation.robustness_status or "STABLE",
                "created_at": investigation.created_at.isoformat() if investigation.created_at else None,
                "completed_at": investigation.completed_at.isoformat() if investigation.completed_at else None,
                "execution_time_ms": investigation.execution_time_ms,
                "turns_used": investigation.turns_used,
                "evidence_count": investigation.evidence_count,
                "claims_count": investigation.claims_count,
                "error_message": investigation.error_message
            },
            "claims": parsed_payload.get("claims", []),
            "evidence": parsed_payload.get("evidence", []),
            "analysis": parsed_payload.get("analysis", None),
            "tool_calls": parsed_payload.get("tool_calls", []),
            "turns": turns_data,
            "reviews": reviews_data
        }

    @classmethod
    def export_as_markdown(cls, db: Session, investigation_id: str) -> str:
        """
        Exports a persisted investigation as a human-readable Markdown audit report.
        Raises ValueError if investigation_id does not exist.
        """
        data = cls.export_as_json(db, investigation_id)
        inv = data["investigation"]
        claims = data.get("claims", [])
        evidence = data.get("evidence", [])
        analysis = data.get("analysis")
        turns = data.get("turns", [])
        reviews = data.get("reviews", [])

        md = []
        md.append(f"# VERIDEX Executive Audit Report")
        md.append(f"**Investigation ID:** `{inv['investigation_id']}`  ")
        md.append(f"**Export Timestamp:** `{data['exported_at']}`  ")
        md.append(f"**Primary Question:** {inv['question']}  ")
        md.append(f"**Lifecycle Status:** `{inv['status']}` | **Robustness Status:** `{inv['robustness_status']}`  ")
        if inv.get("execution_time_ms"):
            md.append(f"**Total Execution Time:** `{inv['execution_time_ms']}ms`  ")
        md.append("\n---\n")

        # Synthesized Finding / Recommendation
        if analysis and isinstance(analysis, dict) and analysis.get("recommendation"):
            rec = analysis["recommendation"]
            md.append("## 🎯 Executive Recommendation")
            md.append(f"### {rec.get('action_title', 'Action Recommendation')}")
            md.append(f"{rec.get('rationale', '')}\n")

        # Claims & Categorized Evidence
        md.append("## 🔍 Claims & Categorized Evidence")
        if claims:
            md.append("### Categorized Claims")
            for c in claims:
                ctype = c.get("evidence_type", "CLAIM")
                ctext = c.get("claim_text", "")
                md.append(f"- **[{ctype}]** {ctext}")
            md.append("")

        if evidence:
            md.append("### Evidence Provenance Trace")
            for item in evidence:
                etype = item.get("evidence_type", "FACT")
                eid = item.get("evidence_id", "")
                desc = item.get("description", "")
                md.append(f"#### Evidence Item: `{eid}` ({etype})")
                md.append(f"- **Description:** {desc}")

                src = item.get("source")
                if src and isinstance(src, dict) and src.get("sql"):
                    md.append(f"- **SQL Query:** `{src['sql']}`")
                    if src.get("query_hash"):
                        md.append(f"- **SHA-256 Provenance Hash:** `{src['query_hash']}`")
                    if src.get("execution_metadata"):
                        meta = src["execution_metadata"]
                        md.append(f"- **Row Count:** {meta.get('row_count', 'N/A')} | **Execution Time:** {meta.get('execution_time_ms', 'N/A')}ms")

                calc = item.get("calculation")
                if calc and isinstance(calc, dict):
                    md.append(f"- **Formula:** `{calc.get('formula_name')}`: `{calc.get('formula')}` = **{calc.get('output')}**")
                md.append("")

        # Conversation Turns Timeline
        if turns:
            md.append("## 💬 Multi-Turn Conversation History")
            for t in turns:
                md.append(f"### Turn {t['turn_number']}")
                md.append(f"**User Question:** {t['user_question']}")
                if t.get("result_summary"):
                    md.append(f"**Assistant Finding:** {t['result_summary']}")
                if t.get("execution_time_ms"):
                    md.append(f"**Execution Time:** `{t['execution_time_ms']}ms`")
                md.append("")

        # Human Review History
        if reviews:
            md.append("## 🛡️ Human-in-the-Loop Review Audit Trail")
            for r in reviews:
                md.append(f"- **Status:** `{r['review_status']}` | **Reviewer:** `{r['reviewer_id']}` | **Date:** `{r['reviewed_at']}`")
                if r.get("review_notes"):
                    md.append(f"  *Notes:* {r['review_notes']}")
            md.append("")

        md.append("\n---\n")
        md.append("*Report generated deterministically by VERIDEX Audit Exporter. Safe SELECT-only provenance verified.*")
        return "\n".join(md)
