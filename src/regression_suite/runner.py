"""Test runner — orchestrates checks with timeout, error isolation, parallel execution."""
from __future__ import annotations

import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime

from .core import CheckPort, CheckResult, CheckStatus, ReporterPort, SuiteResult

logger = logging.getLogger(__name__)


def _run_with_timeout(check: CheckPort) -> CheckResult:
    """Run a check with timeout and error isolation."""
    start = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(check.run)
            try:
                return future.result(timeout=check.timeout_seconds)
            except FutureTimeout:
                elapsed = (time.perf_counter() - start) * 1000
                return CheckResult(
                    name=check.name,
                    suite=check.suite,
                    status=CheckStatus.TIMEOUT,
                    message=f"Timed out after {check.timeout_seconds}s",
                    duration_ms=elapsed,
                    severity=check.severity,
                )
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        return CheckResult(
            name=check.name,
            suite=check.suite,
            status=CheckStatus.ERROR,
            message="Unexpected error",
            duration_ms=elapsed,
            severity=check.severity,
            error=traceback.format_exc(),
        )


class RegressionRunner:
    """Orchestrates regression check execution."""

    def __init__(
        self,
        reporters: list[ReporterPort] | None = None,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> None:
        self._checks: list[CheckPort] = []
        self._reporters = reporters or []
        self._parallel = parallel
        self._max_workers = max_workers

    def register(self, check: CheckPort) -> None:
        self._checks.append(check)

    def register_many(self, checks: list[CheckPort]) -> None:
        for check in checks:
            self.register(check)

    def run_all(
        self,
        suite_filter: str | None = None,
        config: dict | None = None,
    ) -> SuiteResult:
        checks = [c for c in self._checks if not suite_filter or c.suite == suite_filter]
        suite_name = suite_filter or "full-regression"
        result = SuiteResult(
            suite_name=suite_name,
            started_at=datetime.utcnow(),
            config_used=config or {},
        )

        logger.info(f"Starting '{suite_name}' with {len(checks)} checks")

        if self._parallel and len(checks) > 1:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                result.results = list(pool.map(_run_with_timeout, checks))
        else:
            for i, check in enumerate(checks, 1):
                logger.info(f"  [{i}/{len(checks)}] {check.name}")
                r = _run_with_timeout(check)
                status_tag = r.status.value[:4]
                logger.info(f"  [{status_tag}] {check.name} ({r.duration_ms:.0f}ms) — {r.message}")
                result.results.append(r)

        result.finished_at = datetime.utcnow()
        logger.info(
            f"'{suite_name}': {result.passed_count}/{result.total} passed"
            f" ({result.pass_rate:.0%}) in {result.duration_ms:.0f}ms"
        )

        for failure in result.critical_failures:
            logger.error(f"CRITICAL: {failure.name} — {failure.message}")

        for reporter in self._reporters:
            try:
                reporter.report(result)
            except Exception as e:
                logger.error(f"Reporter {type(reporter).__name__} failed: {e}")

        return result
