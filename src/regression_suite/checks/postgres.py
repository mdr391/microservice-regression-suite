"""PostgreSQL regression checks — connectivity, read/write, schema, performance."""
from __future__ import annotations

import time

from ..core import CheckPort, CheckResult, CheckSeverity, CheckStatus


class PostgresConnectCheck(CheckPort):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @property
    def name(self) -> str:
        return "postgres.connectivity"

    @property
    def suite(self) -> str:
        return "postgres"

    @property
    def severity(self) -> CheckSeverity:
        return CheckSeverity.CRITICAL

    @property
    def timeout_seconds(self) -> float:
        return 5.0

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import psycopg2

            conn = psycopg2.connect(self._dsn, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1
            conn.close()
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.PASS,
                message=f"Connected in {elapsed:.0f}ms",
                duration_ms=elapsed,
                severity=self.severity,
            )
        except ImportError:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.SKIP,
                message="psycopg2 not installed",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.FAIL,
                message=f"Connection failed: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
                error=str(e),
            )


class PostgresReadWriteCheck(CheckPort):
    """Idempotent: insert → read → verify → cleanup."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @property
    def name(self) -> str:
        return "postgres.read_write"

    @property
    def suite(self) -> str:
        return "postgres"

    @property
    def severity(self) -> CheckSeverity:
        return CheckSeverity.CRITICAL

    def run(self) -> CheckResult:
        start = time.perf_counter()
        test_id = f"REGTEST-{int(time.time())}"
        try:
            import psycopg2

            conn = psycopg2.connect(self._dsn, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sensor_readings (sensor_id, value, recorded_at)"
                    " VALUES (%s, %s, NOW()) RETURNING reading_id",
                    (test_id, 99.99),
                )
                row_id = cur.fetchone()[0]
                conn.commit()
                cur.execute(
                    "SELECT sensor_id, value FROM sensor_readings WHERE reading_id = %s",
                    (row_id,),
                )
                row = cur.fetchone()
                assert row and row[0] == test_id and float(row[1]) == 99.99
                cur.execute("DELETE FROM sensor_readings WHERE reading_id = %s", (row_id,))
                conn.commit()
            conn.close()
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.PASS,
                message=f"Write/read/verify/cleanup in {elapsed:.0f}ms",
                duration_ms=elapsed,
                severity=self.severity,
            )
        except ImportError:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.SKIP,
                message="psycopg2 not installed",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.FAIL,
                message=f"Read/write failed: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
                error=str(e),
            )


class PostgresSchemaCheck(CheckPort):
    """Verify expected tables and columns exist."""

    EXPECTED = {
        "sensor_readings": ["reading_id", "sensor_id", "value", "recorded_at"],
        "sensors": ["sensor_id", "location", "unit", "active"],
    }

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    @property
    def name(self) -> str:
        return "postgres.schema_integrity"

    @property
    def suite(self) -> str:
        return "postgres"

    @property
    def severity(self) -> CheckSeverity:
        return CheckSeverity.HIGH

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import psycopg2

            conn = psycopg2.connect(self._dsn, connect_timeout=3)
            missing_tables, missing_cols = [], []
            with conn.cursor() as cur:
                for table, cols in self.EXPECTED.items():
                    cur.execute(
                        "SELECT EXISTS(SELECT 1 FROM information_schema.tables"
                        " WHERE table_name=%s AND table_schema='public')",
                        (table,),
                    )
                    if not cur.fetchone()[0]:
                        missing_tables.append(table)
                        continue
                    cur.execute(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name=%s AND table_schema='public'",
                        (table,),
                    )
                    actual = {r[0] for r in cur.fetchall()}
                    missing_cols.extend(f"{table}.{c}" for c in cols if c not in actual)
            conn.close()
            elapsed = (time.perf_counter() - start) * 1000
            if missing_tables or missing_cols:
                return CheckResult(
                    name=self.name,
                    suite=self.suite,
                    status=CheckStatus.FAIL,
                    message="Schema drift detected",
                    duration_ms=elapsed,
                    severity=self.severity,
                    details={"missing_tables": missing_tables, "missing_columns": missing_cols},
                )
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.PASS,
                message=f"All {len(self.EXPECTED)} tables verified",
                duration_ms=elapsed,
                severity=self.severity,
            )
        except ImportError:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.SKIP,
                message="psycopg2 not installed",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.FAIL,
                message=f"Schema check failed: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
                error=str(e),
            )


class PostgresQueryPerformanceCheck(CheckPort):
    """Verify critical queries execute within latency SLO."""

    def __init__(self, dsn: str, max_latency_ms: float = 500.0) -> None:
        self._dsn = dsn
        self._max = max_latency_ms

    @property
    def name(self) -> str:
        return "postgres.query_performance"

    @property
    def suite(self) -> str:
        return "postgres"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import psycopg2

            conn = psycopg2.connect(self._dsn, connect_timeout=3)
            with conn.cursor() as cur:
                t = time.perf_counter()
                cur.execute(
                    "SELECT sensor_id, COUNT(*), AVG(value) FROM sensor_readings"
                    " WHERE recorded_at >= NOW() - INTERVAL '24 hours'"
                    " GROUP BY sensor_id ORDER BY COUNT(*) DESC LIMIT 10"
                )
                cur.fetchall()
                query_ms = (time.perf_counter() - t) * 1000
            conn.close()
            elapsed = (time.perf_counter() - start) * 1000
            passed = query_ms <= self._max
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                message=f"Query {query_ms:.0f}ms (SLO: {self._max}ms)",
                duration_ms=elapsed,
                severity=self.severity,
                details={"query_latency_ms": round(query_ms, 2)},
            )
        except ImportError:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.SKIP,
                message="psycopg2 not installed",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
            )
        except Exception as e:
            return CheckResult(
                name=self.name,
                suite=self.suite,
                status=CheckStatus.FAIL,
                message=f"Performance check failed: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
                severity=self.severity,
                error=str(e),
            )
