"""Benchmark endpoints."""

from typing import List

from fastapi import APIRouter, Depends

from siha.db import get_session
from siha.models import Benchmark
from sqlmodel import select
from siha.benchmarks.runner import get_benchmark_trend
from siha.portal.auth import verify_auth
from siha.schemas import BenchmarkItem, BenchmarkTrend, BenchmarkRunAllResponse

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("", response_model=List[BenchmarkItem])
def get_benchmarks(token: str = Depends(verify_auth)):
    """Get all benchmarks."""
    with get_session() as session:
        benchmarks = session.exec(select(Benchmark)).all()
        return [
            BenchmarkItem(
                id=b.id,
                name=b.name,
                category=b.category,
                origin=b.origin,
                created_ts=b.created_ts.isoformat(),
            )
            for b in benchmarks
        ]


@router.get("/trend", response_model=BenchmarkTrend)
def get_benchmark_trend_endpoint(token: str = Depends(verify_auth)):
    """Get benchmark trend data."""
    return BenchmarkTrend(**get_benchmark_trend())


@router.post("/run-all", response_model=BenchmarkRunAllResponse)
def run_all_benchmarks(token: str = Depends(verify_auth)):
    """Run all benchmarks against the current active harness version."""
    from siha.benchmarks.runner import BenchmarkRunner, seed_benchmarks

    seed_benchmarks()
    runner = BenchmarkRunner()
    with get_session() as session:
        benchmarks = session.exec(select(Benchmark)).all()
    results = []
    for benchmark in benchmarks:
        run = runner.run_benchmark(benchmark, None)
        results.append({
            "name": benchmark.name,
            "score": run.score,
            "passed": run.passed,
        })
    return BenchmarkRunAllResponse(results=results)
