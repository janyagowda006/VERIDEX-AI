import sys
import os
import tempfile
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.business_data import Base
from app.services.data_ingestion import ingest_csv_to_db
from scripts.generate_data import generate_synthetic_data
from app.ai.provider import MockLLMProvider, get_llm_provider, GeminiProvider
from app.ai.eval.evaluator import BenchmarkRunner
from app.ai.eval.schemas import BenchmarkReport


def create_eval_db_session():
    """
    Creates an in-memory SQLite database session populated with synthetic business data for evaluation.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    with tempfile.TemporaryDirectory() as tmp_dir:
        generate_synthetic_data(seed=42, output_dir=tmp_dir)
        ingest_csv_to_db(tmp_dir, session)

    return session


def format_report_markdown(report: BenchmarkReport) -> str:
    """
    Formats a BenchmarkReport into a clean, human-readable markdown evaluation document.
    """
    md = []
    md.append("================================================================================")
    md.append("VERIDEX AI BENCHMARK & EVALUATION REPORT")
    md.append("================================================================================")
    md.append(f"Timestamp:          {report.timestamp}")
    md.append(f"Benchmark Version:  {report.benchmark_version}")
    md.append(f"LLM Provider:       {report.provider_name.upper()}")
    md.append(f"Total Cases:        {report.total_cases}")
    md.append(f"Successful Cases:   {report.successful_cases} ({round(report.successful_cases / report.total_cases * 100, 1)}%)")
    md.append(f"Failed Cases:       {report.failed_cases}")
    md.append("--------------------------------------------------------------------------------")
    md.append("AGGREGATE AI QUALITY METRICS:")
    md.append(f"  * SQL Execution Success Rate:   {round(report.sql_execution_success_rate * 100, 1)}%")
    md.append(f"  * Claim Groundedness Rate:      {round(report.groundedness_rate * 100, 1)}%")
    md.append(f"  * Citation Precision:           {round(report.citation_precision * 100, 1)}%")
    md.append(f"  * Citation Recall:              {round(report.citation_recall * 100, 1)}%")
    md.append(f"  * Unsupported Claim Rate:       {round(report.unsupported_claim_rate * 100, 1)}%")
    md.append(f"  * Decision Agreement Rate:      {round(report.decision_agreement_rate * 100, 1)}%")
    md.append(f"  * Robustness Agreement Rate:    {round(report.robustness_agreement_rate * 100, 1)}%")
    md.append(f"  * Average Turn Latency:         {report.average_latency_ms} ms")
    md.append("================================================================================")
    md.append("PER-CASE EVALUATION BREAKDOWN:")
    md.append("--------------------------------------------------------------------------------")

    for case in report.case_evaluations:
        status_symbol = "[PASS]" if case.success else "[FAIL]"
        md.append(f"{status_symbol} {case.item_id} [{case.category.value}] - {case.question}")
        md.append(f"       Latency: {case.execution_time_ms}ms | Turns: {case.turns_used} | Tools: {case.tool_calls_count}")
        md.append(f"       SQL Success: {case.sql_success} | Evidence: {case.evidence_count} | Claims: {case.claims_count} (Unsupported: {case.unsupported_claims_count})")
        if case.tables_accessed:
            md.append(f"       Tables: {', '.join(case.tables_accessed)}")
        if case.decision_agreement is not None:
            md.append(f"       Decision Agreement: {case.decision_agreement}")
        if case.error_message:
            md.append(f"       Error: {case.error_message}")
        md.append("")

    md.append("================================================================================")
    return "\n".join(md)


def main():
    use_live = "--live" in sys.argv
    provider_name = "gemini" if use_live else "mock"
    print(f"[VERIDEX EVAL] Initializing evaluation pipeline using {provider_name.upper()} provider...")

    db_session = create_eval_db_session()

    if use_live:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: --live mode specified but GEMINI_API_KEY is not set in environment.")
            sys.exit(1)
        provider = GeminiProvider(api_key=api_key)
    else:
        provider = MockLLMProvider()

    runner = BenchmarkRunner()
    report = runner.run_benchmark(db=db_session, provider=provider, max_turns=3, provider_name=provider_name)
    db_session.close()

    formatted_md = format_report_markdown(report)
    print(formatted_md)


if __name__ == "__main__":
    main()
