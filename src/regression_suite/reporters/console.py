"""Color-coded console reporter."""
from __future__ import annotations

from ..core import CheckStatus, ReporterPort, SuiteResult

_C = {
    CheckStatus.PASS: "\033[92m",
    CheckStatus.FAIL: "\033[91m",
    CheckStatus.ERROR: "\033[93m",
    CheckStatus.TIMEOUT: "\033[95m",
    CheckStatus.SKIP: "\033[90m",
}
_R, _B = "\033[0m", "\033[1m"


class ConsoleReporter(ReporterPort):
    def __init__(self, use_color: bool = True) -> None:
        self._color = use_color

    def _c(self, s: CheckStatus, t: str) -> str:
        return f"{_C.get(s, '')}{t}{_R}" if self._color else t

    def report(self, sr: SuiteResult) -> None:
        print(f"\n{'=' * 64}")
        print(f"  REGRESSION SUITE: {sr.suite_name}")
        print(f"  {sr.started_at:%Y-%m-%d %H:%M:%S UTC}")
        print(f"{'=' * 64}")
        for r in sr.results:
            sev = f"({r.severity.value})" if not r.passed else ""
            status_col = self._c(r.status, f"[{r.status.value:7s}]")
            print(f"  {status_col} {r.name:40s} {r.duration_ms:6.0f}ms  {r.message} {sev}")
        print(f"{'─' * 64}")
        pass_str = self._c(CheckStatus.PASS, str(sr.passed_count))
        fail_str = self._c(CheckStatus.FAIL, str(sr.failed_count))
        err_str = self._c(CheckStatus.ERROR, str(sr.error_count))
        print(
            f"  TOTAL: {sr.total}  |  PASS: {pass_str}  |  FAIL: {fail_str}"
            f"  |  ERROR: {err_str}  |  RATE: {sr.pass_rate:.0%}  |  TIME: {sr.duration_ms:.0f}ms"
        )
        if sr.critical_failures:
            print(f"\n  {_B}CRITICAL FAILURES:{_R}")
            for f in sr.critical_failures:
                print(f"    {self._c(CheckStatus.FAIL, '!')} {f.name}: {f.message}")
        outcome = (
            self._c(CheckStatus.PASS, "  ALL PASSED")
            if sr.all_passed
            else self._c(CheckStatus.FAIL, "  SOME CHECKS FAILED")
        )
        print(f"\n{outcome}\n{'=' * 64}\n")
