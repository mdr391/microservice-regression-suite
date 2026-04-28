"""JSON file reporter — writes timestamped results for trend analysis."""
from __future__ import annotations

import json
import logging
import os

from ..core import ReporterPort, SuiteResult

logger = logging.getLogger(__name__)


class JSONFileReporter(ReporterPort):
    def __init__(self, output_dir: str = "results") -> None:
        self._dir = output_dir

    def report(self, sr: SuiteResult) -> None:
        os.makedirs(self._dir, exist_ok=True)
        filename = f"regression_{sr.suite_name}_{sr.started_at:%Y%m%d_%H%M%S}.json"
        path = os.path.join(self._dir, filename)
        with open(path, "w") as f:
            json.dump(sr.to_dict(), f, indent=2, default=str)
        logger.info(f"Results written to {path}")
