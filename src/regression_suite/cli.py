"""CLI entry point for the regression suite."""
from __future__ import annotations

import argparse
import logging
import sys
import time

from .core import CheckPort, CheckResult, CheckSeverity, CheckStatus
from .reporters.console import ConsoleReporter
from .reporters.json_file import JSONFileReporter
from .reporters.slack import SlackReporter
from .runner import RegressionRunner


class DemoCheck(CheckPort):
    """Mock check for demo mode — no services needed."""

    def __init__(
        self,
        check_name: str,
        check_suite: str,
        sev: CheckSeverity = CheckSeverity.MEDIUM,
        status: CheckStatus = CheckStatus.PASS,
        latency: float = 50.0,
        msg: str = "OK",
    ) -> None:
        self._n = check_name
        self._s = check_suite
        self._sev = sev
        self._st = status
        self._lat = latency
        self._msg = msg

    @property
    def name(self) -> str:
        return self._n

    @property
    def suite(self) -> str:
        return self._s

    @property
    def severity(self) -> CheckSeverity:
        return self._sev

    def run(self) -> CheckResult:
        time.sleep(self._lat / 1000)
        return CheckResult(
            name=self.name,
            suite=self.suite,
            status=self._st,
            message=self._msg,
            duration_ms=self._lat,
            severity=self.severity,
        )


def _demo_checks() -> list[CheckPort]:
    st = CheckStatus
    sv = CheckSeverity
    return [
        DemoCheck(
            "grpc.connectivity", "grpc", sv.CRITICAL, st.PASS, 45,
            "Channel ready at localhost:50051",
        ),
        DemoCheck("grpc.health", "grpc", sv.CRITICAL, st.PASS, 32, "Service SERVING"),
        DemoCheck(
            "grpc.health.SensorService", "grpc", sv.CRITICAL, st.PASS, 28, "SensorService SERVING"
        ),
        DemoCheck("grpc.latency", "grpc", sv.MEDIUM, st.PASS, 120, "Avg latency 24ms (SLO: 200ms)"),
        DemoCheck(
            "postgres.connectivity", "postgres", sv.CRITICAL, st.PASS, 18, "Connected in 18ms"
        ),
        DemoCheck(
            "postgres.read_write",
            "postgres",
            sv.CRITICAL,
            st.PASS,
            65,
            "Write/read/verify/cleanup in 65ms",
        ),
        DemoCheck(
            "postgres.schema_integrity", "postgres", sv.HIGH, st.PASS, 42, "All tables verified"
        ),
        DemoCheck(
            "postgres.query_performance", "postgres", sv.MEDIUM, st.PASS, 88,
            "Query 88ms (SLO: 500ms)",
        ),
        DemoCheck(
            "service.end_to_end_flow",
            "service",
            sv.HIGH,
            st.PASS,
            150,
            "Insert/query/aggregate/cleanup in 150ms",
        ),
        DemoCheck(
            "health.http_endpoint", "health", sv.CRITICAL, st.PASS, 22,
            "Health returned 200 in 22ms",
        ),
        DemoCheck(
            "grpc.latency.SensorService",
            "grpc",
            sv.MEDIUM,
            st.PASS,
            120,
            "Avg latency 24ms (SLO: 200ms)",
        ),
    ]


def _register_live_checks(runner: RegressionRunner, config: dict) -> None:
    from .checks.grpc import GrpcConnectivityCheck, GrpcHealthCheck, GrpcLatencyCheck
    from .checks.postgres import (
        PostgresConnectCheck,
        PostgresQueryPerformanceCheck,
        PostgresReadWriteCheck,
        PostgresSchemaCheck,
    )
    from .checks.service import EndToEndDataFlowCheck, HttpHealthEndpointCheck

    g = config.get("grpc", {})
    p = config.get("postgres", {})
    s = config.get("service", {})
    host, port = g.get("host", "localhost"), g.get("port", 50051)
    runner.register(GrpcConnectivityCheck(host, port))
    for svc in g.get("services", [""]):
        runner.register(GrpcHealthCheck(host, port, svc))
    runner.register(GrpcLatencyCheck(host, port, g.get("max_latency_ms", 200.0)))

    dsn = p.get("dsn", "postgresql://localhost:5432/dat")
    runner.register(PostgresConnectCheck(dsn))
    runner.register(PostgresReadWriteCheck(dsn))
    runner.register(PostgresSchemaCheck(dsn))
    runner.register(PostgresQueryPerformanceCheck(dsn, p.get("max_query_latency_ms", 500.0)))
    runner.register(EndToEndDataFlowCheck(dsn))
    if url := s.get("health_url"):
        runner.register(HttpHealthEndpointCheck(url))


def main() -> None:
    parser = argparse.ArgumentParser(description="Microservice Regression Test Suite")
    parser.add_argument("--config", "-c", help="YAML config file path")
    parser.add_argument("--suite", "-s", choices=["grpc", "postgres", "service", "health"])
    parser.add_argument(
        "--demo", action="store_true", help="Run with mock checks (no services needed)"
    )
    parser.add_argument("--json-output", "-j", help="Directory for JSON results")
    parser.add_argument("--parallel", "-p", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    reporters = [ConsoleReporter(use_color=not args.no_color)]
    config: dict = {}

    if not args.demo:
        if not args.config:
            parser.error("--config required (or use --demo)")
        from .config import load_config

        config = load_config(args.config)
        rpt = config.get("reporting", {})
        if d := (args.json_output or rpt.get("json_output_dir")):
            reporters.append(JSONFileReporter(d))
        if url := rpt.get("slack_webhook"):
            reporters.append(
                SlackReporter(
                    url, rpt.get("slack_channel", "#regression"), rpt.get("slack_on_success", False)
                )
            )
        if (prom := rpt.get("prometheus", {})) and prom.get("enabled"):
                from .reporters.prometheus import PrometheusReporter

                reporters.append(
                    PrometheusReporter(
                        prom["pushgateway_url"],
                        prom.get("job_name", "regression"),
                        prom.get("environment", "staging"),
                    )
                )
    elif args.json_output:
        reporters.append(JSONFileReporter(args.json_output))

    parallel = args.parallel or config.get("runner", {}).get("parallel", False)
    runner = RegressionRunner(reporters=reporters, parallel=parallel)

    if args.demo:
        runner.register_many(_demo_checks())
    else:
        _register_live_checks(runner, config)

    print("\n  Microservice Regression Test Suite")
    print(f"  Mode: {'DEMO' if args.demo else 'LIVE'}  |  Parallel: {parallel}")
    if args.suite:
        print(f"  Suite filter: {args.suite}")
    print()

    result = runner.run_all(suite_filter=args.suite, config=config)
    sys.exit(0 if result.all_passed else (2 if result.critical_failures else 1))
