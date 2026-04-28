"""Slack webhook reporter — posts on failure only (unless configured otherwise)."""
from __future__ import annotations

import logging

from ..core import ReporterPort, SuiteResult

logger = logging.getLogger(__name__)


class SlackReporter(ReporterPort):
    def __init__(
        self,
        webhook_url: str,
        channel: str = "#regression",
        post_on_success: bool = False,
    ) -> None:
        self._url = webhook_url
        self._channel = channel
        self._on_success = post_on_success

    def report(self, sr: SuiteResult) -> None:
        if sr.all_passed and not self._on_success:
            return
        failures = "\n".join(f"- *{r.name}*: {r.message}" for r in sr.results if not r.passed)
        color = "#00e5a0" if sr.all_passed else "#ff5c5c"
        emoji = ":white_check_mark:" if sr.all_passed else ":rotating_light:"
        title = f"{emoji} Regression {'PASSED' if sr.all_passed else 'FAILED'}: {sr.suite_name}"
        payload = {
            "channel": self._channel,
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "fields": [
                        {"title": "Passed", "value": str(sr.passed_count), "short": True},
                        {"title": "Failed", "value": str(sr.failed_count), "short": True},
                    ],
                    "text": failures or "All checks passed.",
                    "footer": f"Regression Suite | {sr.started_at:%Y-%m-%d %H:%M UTC}",
                }
            ],
        }
        try:
            import requests

            requests.post(self._url, json=payload, timeout=5)
            logger.info("Slack notification sent")
        except Exception as e:
            logger.error(f"Slack failed: {e}")
