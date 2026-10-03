"""
Deterministic Fallback Analysis Engine for NexPulse AI Assistant
Generates structured advisory analysis from real incident context when AI is disabled or unavailable.
"""
from typing import Dict, Any, List


class FallbackEngine:
    """Generates factual, evidence-based fallback analysis without external LLM calls."""

    @staticmethod
    def generate_fallback(
        incident_context: Dict[str, Any],
        reason: str = "AI service unavailable or unconfigured"
    ) -> Dict[str, Any]:
        """Creates a deterministic AIAnalysisBase response structure."""
        incident = incident_context.get("incident", {})
        service = incident.get("service", {})
        alert = incident_context.get("originating_alert", {})
        logs = incident_context.get("recent_logs", [])
        metrics = incident_context.get("recent_metrics", [])
        timeline = incident_context.get("timeline", [])

        service_name = service.get("name", "Target Service")
        status = incident.get("status", "open").upper()
        severity = incident.get("severity", "critical").upper()

        summary = (
            f"Incident #{incident.get('id', 'N/A')[:8]} is currently {status} with {severity} severity "
            f"on service '{service_name}'. {reason}. Generated from deterministic database telemetry snapshot."
        )

        evidence_items: List[Dict[str, Any]] = []

        # 1. Alert evidence
        if alert and alert.get("rule_name"):
            rule = alert.get("rule_name")
            curr_val = alert.get("current_value")
            thresh = alert.get("threshold")
            evidence_items.append({
                "source_type": "alert",
                "source_reference": f"Rule: {rule}",
                "observation": f"Triggered when metric reached {curr_val} (threshold: {thresh})."
            })

        # 2. Log evidence
        error_logs = [l for l in logs if l.get("level") in ("ERROR", "CRITICAL", "FATAL")]
        if error_logs:
            last_err = error_logs[0]
            evidence_items.append({
                "source_type": "log",
                "source_reference": f"Level: {last_err.get('level')} @ {last_err.get('timestamp')}",
                "observation": f"Observed log error: '{last_err.get('message')[:120]}'"
            })

        # 3. Metric evidence
        if metrics:
            latest_m = metrics[-1]
            evidence_items.append({
                "source_type": "metric",
                "source_reference": f"Metric: {latest_m.get('metric_name')}",
                "observation": f"Recorded value {latest_m.get('value')} {latest_m.get('unit', '')} at {latest_m.get('timestamp')}."
            })

        # Default evidence fallback if none captured
        if not evidence_items:
            evidence_items.append({
                "source_type": "service",
                "source_reference": f"Service: {service_name}",
                "observation": f"Service status listed as '{service.get('status', 'unknown')}'."
            })

        # Possible causes (advisory hypotheses)
        possible_causes = []
        if alert and alert.get("metric_name") == "error_rate":
            possible_causes.append({
                "statement": "Elevated HTTP 5xx error rate ratio detected across recent service endpoints.",
                "supporting_evidence": ["Originating alert rule triggered on error_rate threshold"],
                "confidence": "high"
            })
        elif alert and alert.get("metric_name") == "avg_latency_ms":
            possible_causes.append({
                "statement": "Service response latency spike exceeding operational SLA bounds.",
                "supporting_evidence": ["Originating alert rule triggered on avg_latency_ms threshold"],
                "confidence": "high"
            })
        else:
            possible_causes.append({
                "statement": "Service degradation or abnormal operational behavior recorded in telemetry metrics.",
                "supporting_evidence": ["Incident state opened"],
                "confidence": "medium"
            })

        next_checks = [
            f"Inspect structured application log streams for service '{service_name}' for unhandled exceptions.",
            "Compare HTTP response latency and error distribution against pre-incident baseline metrics.",
            "Verify database connection pool health and background worker task queue processing times.",
            "Validate active alert rules and check for cascading failure signals across downstream services."
        ]

        return {
            "summary": summary,
            "evidence": evidence_items,
            "possible_causes": possible_causes,
            "next_checks": next_checks,
            "limitations_note": f"Fallback Mode Active: {reason}. Facts are derived directly from database evidence.",
            "status": "fallback"
        }
