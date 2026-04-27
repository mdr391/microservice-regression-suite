"""Core domain models and ports — pure Python, zero infrastructure."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CheckStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"
    TIMEOUT = "TIMEOUT"


class CheckSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CheckResult:
    """Result of a single regression check."""

    name: str
    suite: str
    status: CheckStatus
    message: str
    duration_ms: float
    severity: CheckSeverity = CheckSeverity.MEDIUM
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == CheckStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "suite": self.suite,
            "status": self.status.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "error": self.error,
        }


@dataclass
class SuiteResult:
    """Aggregated result of an entire regression run."""

    suite_name: str
    started_at: datetime
    finished_at: datetime | None = None
    results: list[CheckResult] = field(default_factory=list)
    config_used: dict[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.FAIL)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.ERROR)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total if self.total > 0 else 0.0

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def duration_ms(self) -> float:
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds() * 1000
        return 0.0

    @property
    def critical_failures(self) -> list[CheckResult]:
        return [
            r for r in self.results
            if not r.passed and r.severity == CheckSeverity.CRITICAL
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": round(self.duration_ms, 2),
            "summary": {
                "total": self.total,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "errors": self.error_count,
                "pass_rate": f"{self.pass_rate:.1%}",
            },
            "results": [r.to_dict() for r in self.results],
        }


class CheckPort(ABC):
    """Port: interface every regression check implements."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def suite(self) -> str: ...

    @property
    def severity(self) -> CheckSeverity:
        return CheckSeverity.MEDIUM

    @property
    def timeout_seconds(self) -> float:
        return 10.0

    @abstractmethod
    def run(self) -> CheckResult: ...


class ReporterPort(ABC):
    """Port: interface every reporter implements."""

    @abstractmethod
    def report(self, suite_result: SuiteResult) -> None: ...
