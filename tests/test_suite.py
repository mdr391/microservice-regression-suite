"""Unit tests for the regression suite framework."""
import pytest
from regression_suite.core import CheckPort, CheckResult, CheckSeverity, CheckStatus, SuiteResult
from regression_suite.runner import RegressionRunner, _run_with_timeout
from regression_suite.reporters.console import ConsoleReporter
from datetime import datetime
import time


class PassCheck(CheckPort):
    @property
    def name(self) -> str: return "test.pass"
    @property
    def suite(self) -> str: return "test"
    def run(self) -> CheckResult:
        return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.PASS,
                           message="OK", duration_ms=1.0, severity=self.severity)


class FailCheck(CheckPort):
    @property
    def name(self) -> str: return "test.fail"
    @property
    def suite(self) -> str: return "test"
    @property
    def severity(self) -> CheckSeverity: return CheckSeverity.CRITICAL
    def run(self) -> CheckResult:
        return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.FAIL,
                           message="Something broke", duration_ms=5.0, severity=self.severity)


class ErrorCheck(CheckPort):
    @property
    def name(self) -> str: return "test.error"
    @property
    def suite(self) -> str: return "test"
    def run(self) -> CheckResult:
        raise RuntimeError("Unexpected crash")


class SlowCheck(CheckPort):
    @property
    def name(self) -> str: return "test.slow"
    @property
    def suite(self) -> str: return "test"
    @property
    def timeout_seconds(self) -> float: return 0.1
    def run(self) -> CheckResult:
        time.sleep(5)
        return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.PASS,
                           message="Should not reach here", duration_ms=0, severity=self.severity)


class TestCheckResult:
    def test_pass_result(self):
        r = CheckResult(name="x", suite="y", status=CheckStatus.PASS, message="ok", duration_ms=1.0)
        assert r.passed is True
        assert r.to_dict()["status"] == "PASS"

    def test_fail_result(self):
        r = CheckResult(name="x", suite="y", status=CheckStatus.FAIL, message="bad", duration_ms=1.0)
        assert r.passed is False


class TestSuiteResult:
    def test_empty_suite(self):
        sr = SuiteResult(suite_name="test", started_at=datetime.utcnow())
        assert sr.total == 0
        assert sr.pass_rate == 0.0

    def test_mixed_results(self):
        sr = SuiteResult(suite_name="test", started_at=datetime.utcnow(), results=[
            CheckResult(name="a", suite="t", status=CheckStatus.PASS, message="ok", duration_ms=1),
            CheckResult(name="b", suite="t", status=CheckStatus.FAIL, message="bad", duration_ms=2, severity=CheckSeverity.CRITICAL),
        ])
        assert sr.total == 2
        assert sr.passed_count == 1
        assert sr.failed_count == 1
        assert sr.pass_rate == 0.5
        assert not sr.all_passed
        assert len(sr.critical_failures) == 1


class TestRunner:
    def test_all_pass(self):
        runner = RegressionRunner()
        runner.register(PassCheck())
        result = runner.run_all()
        assert result.all_passed
        assert result.total == 1

    def test_error_isolation(self):
        runner = RegressionRunner()
        runner.register(PassCheck())
        runner.register(ErrorCheck())
        runner.register(PassCheck())
        result = runner.run_all()
        assert result.total == 3
        assert result.passed_count == 2
        assert result.error_count == 1

    def test_timeout_protection(self):
        runner = RegressionRunner()
        runner.register(SlowCheck())
        result = runner.run_all()
        assert result.results[0].status == CheckStatus.TIMEOUT

    def test_suite_filter(self):
        runner = RegressionRunner()
        runner.register(PassCheck())  # suite="test"
        result = runner.run_all(suite_filter="nonexistent")
        assert result.total == 0

    def test_mixed_pass_fail(self):
        runner = RegressionRunner()
        runner.register(PassCheck())
        runner.register(FailCheck())
        result = runner.run_all()
        assert not result.all_passed
        assert result.passed_count == 1
        assert result.failed_count == 1
        assert len(result.critical_failures) == 1
