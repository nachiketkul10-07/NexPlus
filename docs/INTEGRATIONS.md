# Connect an application to NexPulse

NexPulse accepts telemetry over HTTP. A service registered in **Services** gets one stable identifier and one independent ingestion key. Applications connect by sending telemetry from their server-side runtime; NexPulse does not fetch or execute source repositories.

## Service setup

1. Sign in and open **Services → Connect application**.
2. Enter an application name, confirm its suggested unique identifier, and choose its environment. Framework, language, and public app URL are optional metadata.
3. Copy the generated `pik_live_…` key once. The API stores only its SHA-256 digest and returns the raw key only on creation or rotation.
4. Save the three `NEXPULSE_*` values in the application's server-side secret manager. Never commit the key, put it in a `VITE_*` variable, or expose it to browser JavaScript.
5. Use **Send test event** in the creation dialog. This stores a labeled `/nexpulse/connection-check` event. A successful result proves key authentication and database persistence.

Admins can rotate a key (the old key stops working immediately), revoke it, deactivate a service, reactivate it, or delete the service and its data. Inactive services reject ingestion with HTTP 403. A revoked or otherwise unknown key receives HTTP 401. After rotating or revoking, update the connected runtime secret and restart/redeploy that runtime.

For Streamlit Community Cloud, paste these TOML values into **App settings → Secrets**, replacing them with the one-time values shown by NexPulse:

```toml
NEXPULSE_API_URL = "https://<nexpulse-host>/api/v1/telemetry"
NEXPULSE_SERVICE_ID = "my-app-production"
NEXPULSE_INGEST_KEY = "<copy-the-one-time-key>"
```

Copy [`examples/python/nexpulse_client.py`](../examples/python/nexpulse_client.py) into the Streamlit app repository, then initialize it server-side:

```python
import streamlit as st
from nexpulse_client import NexPulseClient

nexpulse = NexPulseClient(
    api_url=st.secrets["NEXPULSE_API_URL"],
    service_id=st.secrets["NEXPULSE_SERVICE_ID"],
    ingest_key=st.secrets["NEXPULSE_INGEST_KEY"],
)

nexpulse.send("events", {
    "method": "POST", "endpoint": "/plan/generate", "status_code": 200,
    "duration_ms": 120, "outcome": "success",
})
```

Keep these values in Streamlit Secrets, never in source code. After saving secrets, reboot the app and verify a new request appears in the service detail view.

## HTTP contract

Base path: `https://<nexpulse-host>/api/v1/telemetry`

Send a server-to-server `POST` with `Content-Type: application/json`, `X-Ingest-Key: <service-key>`, and one JSON record or a JSON array of up to 100 records. `service_id` should be the service identifier shown in NexPulse; it may be omitted because the credential itself selects the service. If supplied, an ID belonging to another service is rejected with 403. Timestamps accept ISO-8601 values within the last 30 days and one hour into the future. Records without timestamps use server receive time.

### Events — `POST /events`

Fields: `service_id` (recommended), `timestamp`, `request_id`, `method`, `endpoint`, `status_code`, `duration_ms` (or `response_time_ms`), `outcome`, `error_type`, `error_message`, and `metadata`.

```json
{
  "service_id": "my-api-production",
  "timestamp": "2026-10-11T12:00:00Z",
  "method": "GET",
  "endpoint": "/api/health",
  "status_code": 200,
  "duration_ms": 42,
  "outcome": "success",
  "metadata": {"region": "ap-south-1"}
}
```

An accepted event is stored and also derives request-count, latency, and error metric samples plus a structured log. These derived records are in addition to explicitly submitted metrics and logs.

### Metrics — `POST /metrics`

Fields: `service_id`, `metric_name`, finite numeric `value`, `window_seconds` (1–86400, default 60), optional `timestamp` / `recorded_at`, and string `labels` (up to 10 pairs).

```json
{"service_id":"my-api-production","metric_name":"queue_depth","value":7,"window_seconds":60,"labels":{"queue":"emails"}}
```

### Logs — `POST /logs`

Fields: `service_id`, `timestamp` / `occurred_at`, `level` (`DEBUG`, `INFO`, `WARN`, `WARNING`, `ERROR`, `CRITICAL`, `FATAL`), required `message`, optional `request_id`, `trace_id`, `stack_trace`, and `metadata`.

```json
{"service_id":"my-api-production","level":"ERROR","message":"Payment provider timed out","request_id":"req-123"}
```

Successful writes return HTTP 202 with `{"status":"accepted","accepted_count":1,"rejected_count":0,"request_id":"…"}`. The API commits each write before returning acceptance. Errors use the standard `error.code`, `error.message`, and `error.request_id` envelope. A single batch may contain at most 100 items; request bodies are additionally bounded by the server payload limit. Avoid sending credentials, personal data, or full secrets in messages and metadata; known sensitive metadata keys are redacted.

The API does not currently deduplicate retried records. Do not automatically retry 4xx responses. For network timeouts or 5xx responses, retry only a small bounded number of times with exponential backoff and jitter; a timeout can mean the server committed before the response was lost, so a retry may create a duplicate. Respect `Retry-After` on HTTP 429. Production rate limits are per service (default 600 requests/minute) and use Redis; production fails closed with 503 if the shared limiter is unavailable.

## Python

Copy [`examples/python/nexpulse_client.py`](../examples/python/nexpulse_client.py) into the application or add it to its source tree. It uses only the Python standard library.

Configure server-side variables:

```text
NEXPULSE_API_URL=https://<nexpulse-host>/api/v1/telemetry
NEXPULSE_SERVICE_ID=my-api-production
NEXPULSE_INGEST_KEY=<copy-the-one-time-key>
```

```python
from nexpulse_client import client_from_environment

client = client_from_environment()
client.send("events", {
    "method": "GET", "endpoint": "/health", "status_code": 200,
    "duration_ms": 12, "outcome": "success",
})
client.send("metrics", {"metric_name": "queue_depth", "value": 7})
client.send("logs", {"level": "INFO", "message": "Worker started"})
```

The helper adds the configured `service_id`, uses a bounded timeout, retries only 429/5xx/network errors a small number of times, and never includes the key in exception messages. Its retries are at-least-once and may duplicate a write after a lost response.

## Node.js

Use the standard `fetch` client in [`examples/node/nexpulse.mjs`](../examples/node/nexpulse.mjs). Define the same three `NEXPULSE_*` values in the runtime's secret manager, then call `sendNexPulse("events", record)`, `sendNexPulse("metrics", record)`, or `sendNexPulse("logs", record)`. Keep the key server-side; do not call this from browser code.

## PowerShell smoke test

Paste this in PowerShell. It prompts for the key without placing it in command history. Use the exact registered identifier.

```powershell
$key = Read-Host "Paste the NexPulse ingestion key"
$body = @{
  service_id = "my-api-production"
  method = "GET"
  endpoint = "/health"
  status_code = 200
  duration_ms = 12
  outcome = "success"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "https://<nexpulse-host>/api/v1/telemetry/events" `
  -Headers @{ "X-Ingest-Key" = $key } `
  -ContentType "application/json" `
  -Body $body
Remove-Variable key
```

## Troubleshooting

| HTTP | Meaning | Check |
| --- | --- | --- |
| 401 | Missing/unknown key; the supplied key's digest does not match a stored service key. | Header is exactly `X-Ingest-Key`; no quotes/spaces copied with the key; runtime secret updated and app restarted; key was created/rotated in the same active NexPulse deployment/database. Never send the key in chat. |
| 403 | Credential is recognized but the service is inactive, or a supplied `service_id` belongs to another service. | Reactivate service or use the exact identifier attached to that key. |
| 404 | Wrong API hostname/path or route not present in that deployment. | Use `/api/v1/telemetry/events`, `/metrics`, or `/logs` on the deployed NexPulse hostname. |
| 422 | Invalid schema, timestamp, metric value, or empty/oversized item batch. | Compare payload against the endpoint schema above. |
| 429 | Per-service rate limit exceeded. | Honor `Retry-After`; reduce event volume or batch records. |
| 5xx | API or persistence failure; the record was not acknowledged as accepted. | Retry a bounded number of times, then check backend request ID and service health. |

For the AI Study Planner reports received on 2026-10-11, the client reached an API that returned HTTP 401 for events, metrics and logs. In this code, that response occurs before payload validation, when the supplied key's SHA-256 digest is not found. The deployed service/database and the configured Streamlit secret values cannot be inspected from the local repository. Therefore the evidence rules out a payload-shape or service-id 403 issue, but does not distinguish a stale/mistyped runtime secret from a production deployment/database mismatch. Do not rotate again until comparing the intended deployment and active service record. The admin key-rotation action now explicitly commits the new digest before revealing it; after deployment, rotate once, copy into Streamlit secrets, save and reboot the Streamlit app, then use its first send or the UI test event to confirm 202.

## Query and dashboard

Authenticated operators can query persisted data at `GET /api/v1/telemetry/events`, `/metrics`, and `/logs` with optional `service_id`, time range, and bounded `limit` filters. Service detail reads these persisted records and shows recent request activity, errors, latency, metrics, logs, alerts, and incidents. Service records show **Never connected**, **Receiving** (signal within five minutes), **Stale**, or **Inactive** based on `last_seen_at` and lifecycle state. All accounts currently share one private workspace; this code is not organization-scoped public SaaS.
