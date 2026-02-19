"""
latacc_common/tracing/__init__.py

OpenTelemetry tracing setup for LATACC agents.
Exports traces directly to Jaeger via OTLP/gRPC.
Graceful degradation: if Jaeger is unavailable, tracing is a no-op.
"""

import json
import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)

_initialized = False


def init_tracing(
    service_name: str = "cmop-observer",
    otlp_endpoint: str = "http://localhost:4317",
) -> trace.Tracer:
    """
    Initialise OpenTelemetry tracing with OTLP/gRPC export to Jaeger.

    Call once at application startup. Returns a tracer instance.
    If the OTLP endpoint is unreachable, tracing degrades gracefully
    (spans are created but not exported).

    Args:
        service_name: Service name shown in Jaeger UI.
        otlp_endpoint: OTLP gRPC endpoint (Jaeger default: localhost:4317).

    Returns:
        A configured Tracer instance.
    """
    global _initialized

    if _initialized:
        return trace.get_tracer(service_name)

    resource = Resource.create({"service.name": service_name})

    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info(
            "OTel tracing enabled → %s (service: %s)",
            otlp_endpoint,
            service_name,
        )
    except Exception as exc:
        logger.warning(
            "OTel exporter init failed (%s). Tracing will be no-op.", exc
        )

    trace.set_tracer_provider(provider)
    _initialized = True

    return trace.get_tracer(service_name)


def get_tracer(name: str = "cmop-observer") -> trace.Tracer:
    """Get the global tracer. Call init_tracing() first."""
    return trace.get_tracer(name)


def truncate_json(data: Any, max_chars: int = 4000) -> str:
    """
    Serialize data to JSON and truncate for span attributes.

    OTel attribute values have practical size limits.
    Truncation ensures we capture enough for debugging
    without blowing up the trace backend.
    """
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(data)

    if len(text) > max_chars:
        return text[:max_chars] + f"... [truncated, total {len(text)} chars]"
    return text


def record_error(span: trace.Span, exc: Exception) -> None:
    """Record an exception on a span and set error status."""
    span.set_status(StatusCode.ERROR, str(exc))
    span.record_exception(exc)


__all__ = [
    "get_tracer",
    "init_tracing",
    "record_error",
    "truncate_json",
]