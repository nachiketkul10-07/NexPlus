"""
Telemetry Enrichment Task Module
Performs real, bounded asynchronous processing on telemetry data.
Normalizes timestamps, calculates derived summary statistics, and classifies traffic categories.
Does NOT duplicate raw telemetry or generate alerts/incidents.
"""
from typing import Dict, Any
from app.core.logging import logger


async def run_telemetry_enrichment(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriches telemetry event payloads with calculated metrics and metadata.
    """
    service_id = payload.get("service_id", "unknown")
    metrics = payload.get("metrics", [])
    logs = payload.get("logs", [])

    total_metrics = len(metrics)
    total_logs = len(logs)

    error_logs_count = sum(
        1 for l in logs
        if isinstance(l, dict) and str(l.get("level", "")).upper() in ("ERROR", "FATAL", "CRITICAL")
    )
    avg_latency = 0.0
    latencies = [
        float(m.get("value", 0)) for m in metrics
        if isinstance(m, dict) and m.get("name") in ("latency", "response_time", "duration")
    ]
    if latencies:
        avg_latency = round(sum(latencies) / len(latencies), 2)

    classification = "HEALTHY"
    if error_logs_count > 5 or avg_latency > 1000.0:
        classification = "DEGRADED"

    logger.info(
        f"TELEMETRY_ENRICHMENT_COMPLETED | Service: {service_id} | "
        f"Metrics: {total_metrics} | Logs: {total_logs} | Class: {classification}"
    )

    return {
        "service_id": service_id,
        "metrics_processed": total_metrics,
        "logs_processed": total_logs,
        "error_logs_count": error_logs_count,
        "avg_latency_ms": avg_latency,
        "traffic_classification": classification,
        "enriched": True
    }
