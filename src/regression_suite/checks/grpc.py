"""gRPC regression checks — health, connectivity, latency."""
from __future__ import annotations

import time

from ..core import CheckPort, CheckResult, CheckSeverity, CheckStatus


class GrpcHealthCheck(CheckPort):
    """Verify gRPC service health using the standard health protocol."""

    def __init__(self, host: str, port: int, service_name: str = "") -> None:
        self._host, self._port, self._service_name = host, port, service_name

    @property
    def name(self) -> str:
        suffix = f".{self._service_name}" if self._service_name else ""
        return f"grpc.health{suffix}"

    @property
    def suite(self) -> str:
        return "grpc"

    @property
    def severity(self) -> CheckSeverity:
        return CheckSeverity.CRITICAL

    @property
    def timeout_seconds(self) -> float:
        return 5.0

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import grpc
            from grpc_health.v1 import health_pb2, health_pb2_grpc

            channel = grpc.insecure_channel(f"{self._host}:{self._port}")
            stub = health_pb2_grpc.HealthStub(channel)
            response = stub.Check(
                health_pb2.HealthCheckRequest(service=self._service_name), timeout=3.0,
            )
            channel.close()
            elapsed = (time.perf_counter() - start) * 1000
            serving = response.status == health_pb2.HealthCheckResponse.SERVING

            return CheckResult(
                name=self.name, suite=self.suite, severity=self.severity,
                status=CheckStatus.PASS if serving else CheckStatus.FAIL,
                message=f"Service {'SERVING' if serving else response.status} at {self._host}:{self._port}",
                duration_ms=elapsed,
            )
        except ImportError:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.SKIP,
                               message="grpcio-health-checking not installed",
                               duration_ms=(time.perf_counter() - start) * 1000, severity=self.severity)
        except Exception as e:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.FAIL,
                               message=f"Health check failed: {e}",
                               duration_ms=(time.perf_counter() - start) * 1000,
                               severity=self.severity, error=str(e))


class GrpcConnectivityCheck(CheckPort):
    """Verify a gRPC channel can be established."""

    def __init__(self, host: str, port: int) -> None:
        self._host, self._port = host, port

    @property
    def name(self) -> str:
        return "grpc.connectivity"

    @property
    def suite(self) -> str:
        return "grpc"

    @property
    def severity(self) -> CheckSeverity:
        return CheckSeverity.CRITICAL

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import grpc
            channel = grpc.insecure_channel(f"{self._host}:{self._port}")
            grpc.channel_ready_future(channel).result(timeout=3.0)
            channel.close()
            elapsed = (time.perf_counter() - start) * 1000
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.PASS,
                               message=f"Channel ready at {self._host}:{self._port} in {elapsed:.0f}ms",
                               duration_ms=elapsed, severity=self.severity)
        except ImportError:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.SKIP,
                               message="grpcio not installed",
                               duration_ms=(time.perf_counter() - start) * 1000, severity=self.severity)
        except Exception as e:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.FAIL,
                               message=f"Cannot connect: {e}",
                               duration_ms=(time.perf_counter() - start) * 1000,
                               severity=self.severity, error=str(e))


class GrpcLatencyCheck(CheckPort):
    """Verify gRPC call latency is within SLO."""

    def __init__(self, host: str, port: int, max_latency_ms: float = 200.0) -> None:
        self._host, self._port, self._max_latency_ms = host, port, max_latency_ms

    @property
    def name(self) -> str:
        return "grpc.latency"

    @property
    def suite(self) -> str:
        return "grpc"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import grpc
            from grpc_health.v1 import health_pb2, health_pb2_grpc
            channel = grpc.insecure_channel(f"{self._host}:{self._port}")
            stub = health_pb2_grpc.HealthStub(channel)
            stub.Check(health_pb2.HealthCheckRequest(), timeout=3.0)  # warm up

            latencies = []
            for _ in range(5):
                t = time.perf_counter()
                stub.Check(health_pb2.HealthCheckRequest(), timeout=3.0)
                latencies.append((time.perf_counter() - t) * 1000)
            channel.close()
            elapsed = (time.perf_counter() - start) * 1000
            avg = sum(latencies) / len(latencies)

            passed = avg <= self._max_latency_ms
            return CheckResult(
                name=self.name, suite=self.suite,
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                message=f"Avg latency {avg:.0f}ms {'within' if passed else 'exceeds'} SLO {self._max_latency_ms}ms",
                duration_ms=elapsed, severity=self.severity,
                details={"avg_ms": round(avg, 2), "samples": len(latencies)},
            )
        except ImportError:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.SKIP,
                               message="grpcio not installed",
                               duration_ms=(time.perf_counter() - start) * 1000, severity=self.severity)
        except Exception as e:
            return CheckResult(name=self.name, suite=self.suite, status=CheckStatus.FAIL,
                               message=f"Latency check failed: {e}",
                               duration_ms=(time.perf_counter() - start) * 1000,
                               severity=self.severity, error=str(e))
