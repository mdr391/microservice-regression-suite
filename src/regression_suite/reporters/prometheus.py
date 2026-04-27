"""Prometheus Pushgateway reporter — pushes metrics after each run."""
from __future__ import annotations
import logging
from ..core import ReporterPort, SuiteResult

logger = logging.getLogger(__name__)

class PrometheusReporter(ReporterPort):
    def __init__(self, pushgateway_url: str = "http://localhost:9091",
                 job_name: str = "regression", environment: str = "staging") -> None:
        self._url, self._job, self._env = pushgateway_url, job_name, environment

    def report(self, sr: SuiteResult) -> None:
        try:
            from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
        except ImportError:
            logger.warning("prometheus_client not installed"); return

        reg = CollectorRegistry()
        cs = Gauge("regression_check_status", "1=pass 0=fail", ["check_name","suite","severity","environment"], registry=reg)
        cd = Gauge("regression_check_duration_ms", "Check latency", ["check_name","suite","environment"], registry=reg)
        for r in sr.results:
            cs.labels(check_name=r.name, suite=r.suite, severity=r.severity.value, environment=self._env).set(1 if r.passed else 0)
            cd.labels(check_name=r.name, suite=r.suite, environment=self._env).set(r.duration_ms)
        Gauge("regression_suite_pass_rate","Pass rate",["suite_name","environment"],registry=reg).labels(suite_name=sr.suite_name,environment=self._env).set(sr.pass_rate)
        Gauge("regression_suite_failures","Failed checks",["suite_name","environment"],registry=reg).labels(suite_name=sr.suite_name,environment=self._env).set(sr.failed_count+sr.error_count)
        Gauge("regression_suite_duration_ms","Suite time",["suite_name","environment"],registry=reg).labels(suite_name=sr.suite_name,environment=self._env).set(sr.duration_ms)
        try:
            push_to_gateway(self._url, job=self._job, registry=reg)
            logger.info(f"Metrics pushed to {self._url}")
        except Exception as e:
            logger.error(f"Push failed: {e}")
