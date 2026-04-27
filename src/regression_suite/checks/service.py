"""Service integration checks — end-to-end data flow, HTTP health."""
from __future__ import annotations

import time

from ..core import CheckPort, CheckResult, CheckSeverity, CheckStatus


class EndToEndDataFlowCheck(CheckPort):
    """Full pipeline: insert → query → aggregate → cleanup."""
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
    @property
    def name(self) -> str: return "service.end_to_end_flow"
    @property
    def suite(self) -> str: return "service"
    @property
    def severity(self) -> CheckSeverity: return CheckSeverity.HIGH

    def run(self) -> CheckResult:
        start = time.perf_counter()
        marker = f"E2E-{int(time.time())}"
        try:
            import psycopg2
            conn = psycopg2.connect(self._dsn, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("INSERT INTO sensor_readings (sensor_id, value, recorded_at) VALUES (%s, %s, NOW()) RETURNING reading_id", (marker, 72.5))
                rid = cur.fetchone()[0]; conn.commit()
                cur.execute("SELECT sensor_id, value FROM sensor_readings WHERE reading_id = %s", (rid,))
                row = cur.fetchone(); assert row and row[0] == marker
                cur.execute("SELECT COUNT(*), AVG(value) FROM sensor_readings WHERE sensor_id = %s", (marker,))
                agg = cur.fetchone(); assert agg[0] >= 1
                cur.execute("DELETE FROM sensor_readings WHERE sensor_id = %s", (marker,)); conn.commit()
            conn.close()
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.PASS,
                               message=f"Insert/query/aggregate/cleanup in {elapsed:.0f}ms", duration_ms=elapsed, severity=self.severity)
        except ImportError:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.SKIP,
                               message="psycopg2 not installed", duration_ms=(time.perf_counter()-start)*1000, severity=self.severity)
        except Exception as e:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.FAIL,
                               message=f"E2E failed: {e}", duration_ms=(time.perf_counter()-start)*1000,
                               severity=self.severity, error=str(e))


class HttpHealthEndpointCheck(CheckPort):
    """Check HTTP /health returns 200."""
    def __init__(self, url: str) -> None:
        self._url = url
    @property
    def name(self) -> str: return "health.http_endpoint"
    @property
    def suite(self) -> str: return "health"
    @property
    def severity(self) -> CheckSeverity: return CheckSeverity.CRITICAL

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import requests
            resp = requests.get(self._url, timeout=3.0)
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult(name=self.name, suite=self.suite,
                               status=CheckStatus.PASS if resp.status_code == 200 else CheckStatus.FAIL,
                               message=f"Health returned {resp.status_code} in {elapsed:.0f}ms",
                               duration_ms=elapsed, severity=self.severity)
        except ImportError:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.SKIP,
                               message="requests not installed", duration_ms=(time.perf_counter()-start)*1000, severity=self.severity)
        except Exception as e:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.FAIL,
                               message=f"Health check failed: {e}", duration_ms=(time.perf_counter()-start)*1000,
                               severity=self.severity, error=str(e))
