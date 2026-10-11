// Framework-neutral Node.js example. Store these values in the runtime secret manager.
const baseUrl = process.env.NEXPULSE_API_URL?.replace(/\/$/, "");
const serviceId = process.env.NEXPULSE_SERVICE_ID;
const ingestKey = process.env.NEXPULSE_INGEST_KEY;

if (!baseUrl || !serviceId || !ingestKey) {
  throw new Error("NEXPULSE_API_URL, NEXPULSE_SERVICE_ID and NEXPULSE_INGEST_KEY are required");
}

export async function sendNexPulse(kind, record) {
  if (!["events", "metrics", "logs"].includes(kind)) throw new Error("Invalid telemetry type");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${baseUrl}/${kind}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Ingest-Key": ingestKey,
      },
      body: JSON.stringify({ ...record, service_id: serviceId }),
      signal: controller.signal,
    });
    if (!response.ok) {
      // Don't log request headers or the credential. Avoid retrying 4xx errors.
      throw new Error(`NexPulse rejected ${kind} telemetry (HTTP ${response.status})`);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

// Example:
// await sendNexPulse("events", { method: "GET", endpoint: "/health", status_code: 200, duration_ms: 12 });
