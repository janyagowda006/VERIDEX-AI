"""
VERIDEX AI Evaluation Framework Package.
Provides deterministic benchmarking, dataset loading, metric evaluation, and CLI reporting.
"""
from app.ai.eval.schemas import (
    BenchmarkItem,
    CaseEvaluation,
    BenchmarkReport
)
from app.ai.eval.evaluator import BenchmarkRunner, ResponseEvaluator

__all__ = [
    "BenchmarkItem",
    "CaseEvaluation",
    "BenchmarkReport",
    "BenchmarkRunner",
    "ResponseEvaluator"
]
