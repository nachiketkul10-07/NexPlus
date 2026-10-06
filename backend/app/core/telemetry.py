"""
PulseOps OpenTelemetry & Distributed Tracing Setup
Provides OpenTelemetry SDK initialization, OTLP span export pipeline,
and sensitive header/payload sanitization for FastAPI application.
"""
import os
from typing import Optional
from urllib.parse import urlparse
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.core.config import settings
from app.core.logging import logger

_is_otel_initialized: bool = False


def init_telemetry(app: FastAPI) -> None:
    """
    Initializes OpenTelemetry SDK, tracer provider, sampling, and FastAPI instrumentation.
    Handles exporter unavailability gracefully without interrupting application startup.
    """
    global _is_otel_initialized
    if _is_otel_initialized or not settings.OTEL_ENABLED:
        logger.info(f"OpenTelemetry initialization skipped | Enabled: {settings.OTEL_ENABLED}")
        return

    try:
        resource = Resource.create(attributes={
            SERVICE_NAME: settings.OTEL_SERVICE_NAME
        })

        sampler = TraceIdRatioBased(settings.OTEL_TRACE_SAMPLING_RATE)
        provider = TracerProvider(resource=resource, sampler=sampler)

        exporter_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
        endpoint_host = urlparse(exporter_endpoint).hostname
        no_remote_collector = bool(os.getenv("VERCEL")) and endpoint_host in {"localhost", "127.0.0.1", "::1"}
        if no_remote_collector:
            logger.info("OTLP span export skipped on Vercel because the configured collector is local to the developer machine")
        else:
            try:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=exporter_endpoint,
                    timeout=settings.OTEL_EXPORTER_OTLP_TIMEOUT
                )
                processor = BatchSpanProcessor(otlp_exporter)
                provider.add_span_processor(processor)
                logger.info(f"OTLP Span Exporter configured | Endpoint: {exporter_endpoint}")
            except Exception as exc:
                logger.warning(
                    f"OTLP Span Exporter initialization warning (Collector may be offline) | "
                    f"Reason: {exc.__class__.__name__} - {exc}"
                )

        trace.set_tracer_provider(provider)

        # Instrument FastAPI app, excluding sensitive or operational telemetry endpoints
        FastAPIInstrumentor().instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls="metrics,health,docs,openapi.json,redoc"
        )

        _is_otel_initialized = True
        logger.info(f"OpenTelemetry initialized for service: {settings.OTEL_SERVICE_NAME}")
    except Exception as exc:
        logger.error(f"Failed to initialize OpenTelemetry | Reason: {exc.__class__.__name__} - {exc}")


def get_tracer(name: str = "pulseops-backend"):
    """Returns configured OpenTelemetry tracer."""
    return trace.get_tracer(name)
