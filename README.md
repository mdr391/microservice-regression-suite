# Microservice Regression Test Suite

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)

A production-grade, periodic regression test suite for verifying **gRPC microservices**, **PostgreSQL databases**, and **service health** in distributed systems. Built with **hexagonal architecture** — the same pattern the services it tests are built with.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    REGRESSION SUITE                          │
│                                                              │
│   Scheduler ──▶ Runner ──▶ Reporters                        │
│   (cron/CI)     (orchestrator)   (console/JSON/Slack/Prom)  │
│                     │                                        │
│        ┌────────────┼────────────┐                          │
│        ▼            ▼            ▼                          │
│   ┌─────────┐ ┌─────────┐ ┌──────────┐                    │
│   │  gRPC   │ │ Postgres │ │ Service  │                    │
│   │ Checks  │ │ Checks   │ │ Checks   │                    │
│   └─────────┘ └─────────┘ └──────────┘                    │
│                                                              │
│   Ports: CheckPort  — interface every check implements      │
│          ReporterPort — interface every reporter implements  │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **11 regression checks** across gRPC, PostgreSQL, and service integration
- **Hexagonal architecture** — checks and reporters are swappable adapters behind ports
- **Timeout protection** — no check can hang forever (configurable per check)
- **Error isolation** — one failing check never blocks the others
- **Idempotent** — creates and cleans up its own test data every run
- **Multiple reporters** — Console (color-coded), JSON file, Slack, Prometheus Pushgateway
- **Severity levels** — CRITICAL/HIGH/MEDIUM/LOW with different alert routing
- **Demo mode** — runs without real services for development and CI
- **YAML config** — separate configs per environment with `${ENV_VAR}` expansion
- **Non-zero exit codes** — integrates with CI pipelines (0=pass, 1=fail, 2=critical)

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/microservice-regression-suite.git
cd microservice-regression-suite
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

regression-suite --demo                           # no services needed
regression-suite --config config/local.yaml       # against live services
regression-suite --demo --suite grpc              # filter by suite
regression-suite --demo --json-output results/    # save JSON report
```

## Checks

| Check | Suite | Severity | Description |
|-------|-------|----------|-------------|
| `grpc.connectivity` | grpc | CRITICAL | Channel can be established |
| `grpc.health` | grpc | CRITICAL | Standard gRPC health protocol |
| `grpc.health.{service}` | grpc | CRITICAL | Named service health |
| `grpc.latency` | grpc | MEDIUM | Round-trip latency within SLO |
| `postgres.connectivity` | postgres | CRITICAL | Database is reachable |
| `postgres.read_write` | postgres | CRITICAL | Insert → read → verify → cleanup |
| `postgres.schema_integrity` | postgres | HIGH | Expected tables/columns exist |
| `postgres.query_performance` | postgres | MEDIUM | Queries within latency SLO |
| `service.end_to_end_flow` | service | HIGH | Full data pipeline works |
| `health.http_endpoint` | health | CRITICAL | HTTP /health returns 200 |

## Adding a Custom Check

```python
from regression_suite.core import CheckPort, CheckResult, CheckStatus, CheckSeverity

class MyCheck(CheckPort):
    @property
    def name(self) -> str: return "custom.my_check"
    @property
    def suite(self) -> str: return "custom"
    @property
    def severity(self) -> CheckSeverity: return CheckSeverity.HIGH

    def run(self) -> CheckResult:
        # your logic here
        return CheckResult(
            name=self.name, suite=self.suite,
            status=CheckStatus.PASS, message="OK", duration_ms=42.0,
            severity=self.severity,
        )
```

## Observability

### Prometheus Metrics

Pushed to Pushgateway after each run: `regression_check_status`, `regression_check_duration_ms`, `regression_suite_pass_rate`, `regression_suite_failures`.

### Alert Rules

Pre-built Prometheus alerts in `deploy/prometheus/rules/`:
- **RegressionCriticalFailure** — critical check failing 2+ min
- **RegressionPassRateLow** — pass rate below 80%
- **RegressionLatencyHigh** — gRPC latency exceeding SLO
- **RegressionSuiteStale** — no results pushed in 30+ min

## Deployment

| Method | File | Description |
|--------|------|-------------|
| **GitHub Actions** | `.github/workflows/ci.yml` | Lint + test on every push/PR |
| **GitLab CI/CD** | `.gitlab-ci.yml` | Scheduled pipeline for staging/prod |
| **Kubernetes** | `deploy/k8s/regression-cronjob.yaml` | CronJob every 15 minutes |
| **Docker** | `deploy/Dockerfile` | Containerized runner |

## Design Principles

1. **Hexagonal architecture** — `CheckPort` and `ReporterPort` are abstract interfaces. Implementations are swappable adapters.
2. **Idempotent execution** — every check creates and cleans up its own test data.
3. **Error isolation** — each check runs in its own thread with a timeout.
4. **Severity-based alerting** — CRITICAL fires Slack immediately. MEDIUM shows on dashboards.
5. **Configuration-driven** — same code, different YAML config per environment.

Copyright © 2026 Zahidur Rahman
