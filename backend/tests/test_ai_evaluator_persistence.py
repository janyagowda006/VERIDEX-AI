import sys
import unittest.mock as mock
from app.ai.eval.evaluator import BenchmarkRunner, ResponseEvaluator
from app.ai.eval.schemas import BenchmarkReport, BenchmarkItem, BenchmarkCategory
from app.ai.provider import MockLLMProvider
from app.models.investigation import Investigation
from app.services.investigation_service import InvestigationService
from app.schemas.ai import AskResponse
from app.ai.eval.cli_eval import main as cli_main, format_report_markdown


def test_benchmark_runs_without_persistence_by_default(test_db_session):
    """
    Verifies that running a benchmark with default settings (persist_investigations=False)
    does not populate investigation_id in CaseEvaluation and does not persist Investigation records.
    """
    db_count_before = test_db_session.query(Investigation).count()

    runner = BenchmarkRunner()
    provider = MockLLMProvider()

    report = runner.run_benchmark(
        db=test_db_session,
        provider=provider,
        max_turns=3,
        provider_name="mock",
        persist_investigations=False
    )

    assert isinstance(report, BenchmarkReport)
    assert report.total_cases == 20
    assert len(report.case_evaluations) == 20

    # Ensure no investigation_ids attached and DB count is unchanged
    for case in report.case_evaluations:
        assert case.investigation_id is None

    db_count_after = test_db_session.query(Investigation).count()
    assert db_count_after == db_count_before


def test_benchmark_runs_with_persistence_enabled(test_db_session):
    """
    Verifies that running a benchmark with persist_investigations=True:
    1. Persists 20 Investigation records in the DB.
    2. Attaches matching investigation_id to each CaseEvaluation.
    3. Populates valid terminal status and result_json on DB records.
    """
    db_count_before = test_db_session.query(Investigation).count()

    runner = BenchmarkRunner()
    provider = MockLLMProvider()

    report = runner.run_benchmark(
        db=test_db_session,
        provider=provider,
        max_turns=3,
        provider_name="mock",
        persist_investigations=True
    )

    assert isinstance(report, BenchmarkReport)
    assert report.total_cases == 20
    assert len(report.case_evaluations) == 20

    # Verify every case evaluation has a valid investigation_id
    persisted_ids = []
    for case in report.case_evaluations:
        assert case.investigation_id is not None
        assert case.investigation_id.startswith("inv_")
        persisted_ids.append(case.investigation_id)

    db_count_after = test_db_session.query(Investigation).count()
    assert db_count_after == db_count_before + 20

    # Inspect persisted records in DB
    db_records = test_db_session.query(Investigation).filter(Investigation.investigation_id.in_(persisted_ids)).all()
    assert len(db_records) == 20

    for rec in db_records:
        assert rec.question is not None
        assert rec.status in ["COMPLETED", "REQUIRES_REVIEW", "FAILED"]
        assert rec.result_json is not None
        assert len(rec.result_json) > 0


def test_persisted_failed_benchmark_investigation(test_db_session):
    """
    Verifies that when run_investigation_loop raises an exception during a benchmark run,
    the investigation is persisted as FAILED with error text and sanitized details.
    """
    runner = BenchmarkRunner()
    provider = MockLLMProvider()

    with mock.patch("app.ai.eval.evaluator.run_investigation_loop", side_effect=RuntimeError("Simulated LLM API error api_key=secret_12345")):
        report = runner.run_benchmark(
            db=test_db_session,
            provider=provider,
            max_turns=3,
            provider_name="mock",
            persist_investigations=True
        )

    assert report.failed_cases == 20
    assert report.successful_cases == 0

    first_case = report.case_evaluations[0]
    assert first_case.investigation_id is not None
    assert first_case.success is False

    # Check DB record for failure status and credential sanitization
    db_rec = test_db_session.query(Investigation).filter(Investigation.investigation_id == first_case.investigation_id).first()
    assert db_rec is not None
    assert db_rec.status == "FAILED"
    assert "api_key=***" in db_rec.error_message
    assert "secret_12345" not in db_rec.error_message


def test_persistence_failure_does_not_corrupt_benchmark_report(test_db_session):
    """
    Verifies that if InvestigationService throws a database exception during persistence,
    the benchmark evaluation result itself succeeds cleanly and remains uncorrupted.
    """
    runner = BenchmarkRunner()
    provider = MockLLMProvider()

    with mock.patch("app.services.investigation_service.InvestigationService.update_investigation_success", side_effect=Exception("DB write failure")):
        report = runner.run_benchmark(
            db=test_db_session,
            provider=provider,
            max_turns=3,
            provider_name="mock",
            persist_investigations=True
        )

    # Benchmark report must still complete successfully
    assert isinstance(report, BenchmarkReport)
    assert report.total_cases == 20
    assert report.successful_cases == 20
    assert report.failed_cases == 0


def test_metrics_identical_with_and_without_persistence(test_db_session):
    """
    Verifies that metric calculation (groundedness, precision, recall, SQL rate, average latency)
    is strictly identical whether persistence is enabled or disabled.
    """
    runner = BenchmarkRunner()
    provider = MockLLMProvider()

    report_no_persist = runner.run_benchmark(
        db=test_db_session,
        provider=provider,
        max_turns=3,
        provider_name="mock",
        persist_investigations=False
    )

    report_persist = runner.run_benchmark(
        db=test_db_session,
        provider=provider,
        max_turns=3,
        provider_name="mock",
        persist_investigations=True
    )

    assert report_no_persist.sql_execution_success_rate == report_persist.sql_execution_success_rate
    assert report_no_persist.groundedness_rate == report_persist.groundedness_rate
    assert report_no_persist.citation_precision == report_persist.citation_precision
    assert report_no_persist.citation_recall == report_persist.citation_recall
    assert report_no_persist.unsupported_claim_rate == report_persist.unsupported_claim_rate
    assert report_no_persist.decision_agreement_rate == report_persist.decision_agreement_rate
    assert report_no_persist.robustness_agreement_rate == report_persist.robustness_agreement_rate


def test_cli_eval_default_vs_persist(capsys):
    """
    Verifies CLI behavior:
    1. Default execution (no flags) runs without persistence.
    2. Execution with --persist flag passes persist_investigations=True and formats IDs in markdown output.
    """
    with mock.patch.object(sys, "argv", ["cli_eval.py"]):
        cli_main()
    captured_default = capsys.readouterr().out
    assert "VERIDEX AI BENCHMARK & EVALUATION REPORT" in captured_default
    assert "Persistence enabled" not in captured_default

    with mock.patch.object(sys, "argv", ["cli_eval.py", "--persist"]):
        cli_main()
    captured_persist = capsys.readouterr().out
    assert "VERIDEX AI BENCHMARK & EVALUATION REPORT" in captured_persist
    assert "Persistence enabled" in captured_persist
    assert "[ID: inv_" in captured_persist
