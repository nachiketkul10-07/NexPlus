"""Small standard-library HTTP client for NexPulse telemetry ingestion."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NexPulseError(RuntimeError):
    def __init__(self, status: int | None, message: str):
        super().__init__(message)
        self.status = status


class NexPulseClient:
    """Send events, metrics, and logs with a service-specific ingestion key.

    `api_url` is the telemetry base URL, ending in `/api/v1/telemetry`.
    Keys are only read from runtime configuration and never included in errors.
    """

    def __init__(
        self,
        api_url: str | None = None,
        service_id: str | None = None,
        ingest_key: str | None = None,
        timeout_seconds: float = 5,
        retries: int = 2,
    ) -> None:
        self.api_url = (api_url or os.environ.get("NEXPULSE_API_URL", "")).rstrip("/")
        self.service_id = service_id or os.environ.get("NEXPULSE_SERVICE_ID", "")
        self.ingest_key = ingest_key or os.environ.get("NEXPULSE_INGEST_KEY", "")
        self.timeout_seconds = min(max(float(timeout_seconds), 0.2), 30.0)
        self.retries = min(max(int(retries), 0), 3)
        if not self.api_url or not self.service_id or not self.ingest_key:
            raise ValueError("NexPulse API URL, service ID, and ingestion key are required")

    def send(self, kind: str, payload: Mapping[str, Any] | list[Mapping[str, Any]]) -> dict[str, Any]:
        if kind not in {"events", "metrics", "logs"}:
            raise ValueError("kind must be events, metrics, or logs")
        values = payload if isinstance(payload, list) else [payload]
        if not values or len(values) > 100:
            raise ValueError("A request must contain between 1 and 100 records")
        records = []
        for record in values:
            item = dict(record)
            supplied_id = item.get("service_id")
            if supplied_id is not None and str(supplied_id) != self.service_id:
                raise ValueError("The payload service_id must match the configured service")
            item["service_id"] = self.service_id
            records.append(item)
        body = json.dumps(records if isinstance(payload, list) else records[0], allow_nan=False).encode("utf-8")
        request = Request(
            f"{self.api_url}/{kind}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Ingest-Key": self.ingest_key,
            },
            method="POST",
        )

        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if not isinstance(result, dict) or result.get("status") != "accepted":
                        raise NexPulseError(response.status, "NexPulse returned an unexpected success response")
                    return result
            except HTTPError as exc:
                if exc.code == 429 or 500 <= exc.code < 600:
                    if attempt < self.retries:
                        retry_after = exc.headers.get("Retry-After", "")
                        try:
                            delay = min(max(float(retry_after), 0), 2.0)
                        except ValueError:
                            delay = min(0.25 * (2**attempt), 1.0)
                        time.sleep(delay)
                        continue
                message = "NexPulse rejected telemetry"
                if exc.code == 401:
                    message = "NexPulse rejected the ingestion credential (HTTP 401)"
                elif exc.code == 403:
                    message = "NexPulse rejected the service identity or inactive service (HTTP 403)"
                elif exc.code == 422:
                    message = "NexPulse rejected the telemetry schema (HTTP 422)"
                elif exc.code == 429:
                    message = "NexPulse rate limit exceeded (HTTP 429)"
                raise NexPulseError(exc.code, message) from None
            except (TimeoutError, URLError, OSError) as exc:
                if attempt < self.retries:
                    time.sleep(min(0.25 * (2**attempt), 1.0))
                    continue
                raise NexPulseError(None, "NexPulse request failed or timed out") from None
        raise NexPulseError(None, "NexPulse request failed")


def client_from_environment() -> NexPulseClient:
    """Construct a client from NEXPULSE_* runtime environment variables."""
    return NexPulseClient()
