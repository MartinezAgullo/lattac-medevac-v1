"""
latacc_common/tools/registry.py

Tool registry with automatic OpenAI-compatible schema generation.
Instrumented with OpenTelemetry: each tool execution creates a span
with arguments, response payload, and duration.
"""

import inspect
import logging
import time
from enum import StrEnum
from typing import Any, Callable, get_type_hints

from opentelemetry import trace

from latacc_common.tracing import record_error, truncate_json

logger = logging.getLogger(__name__)

# Python type → JSON Schema type mapping
_TYPE_MAP: dict[type, str] = {
    int: "integer",
    float: "number",
    bool: "boolean",
    str: "string",
}


def _json_schema_type(hint: type) -> dict[str, Any]:
    """Convert a Python type hint to a JSON Schema property."""
    if isinstance(hint, type) and issubclass(hint, StrEnum):
        return {
            "type": "string",
            "enum": [e.value for e in hint],
        }
    return {"type": _TYPE_MAP.get(hint, "string")}


def _parse_docstring_params(docstring: str) -> dict[str, str]:
    """
    Extract parameter descriptions from Google-style docstrings.

    Parses the 'Args:' section to map parameter names to descriptions.
    """
    params: dict[str, str] = {}
    if not docstring:
        return params

    in_args = False
    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if in_args:
            if stripped and not stripped.startswith("-") and ":" not in stripped:
                break
            if ":" in stripped:
                name, _, desc = stripped.lstrip("- ").partition(":")
                params[name.strip()] = desc.strip()

    return params


class ToolRegistry:
    """
    Central registry for agent tools with auto-schema generation.

    Each tool execution is traced via OpenTelemetry with:
    - tool.name, tool.arguments (as span attributes)
    - tool.response (truncated JSON)
    - tool.duration_ms
    - tool.success (bool)
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}
        self._schemas: list[dict[str, Any]] = []
        self._tracer = trace.get_tracer("latacc.tools")

    def register(self, func: Callable) -> Callable:
        """Register a tool function and auto-generate its OpenAI schema."""
        name = func.__name__
        if name in self._tools:
            logger.warning("Tool '%s' already registered, overwriting.", name)

        self._tools[name] = func
        self._schemas.append(self._build_schema(func))
        logger.debug("Registered tool: %s", name)
        return func

    def _build_schema(self, func: Callable) -> dict[str, Any]:
        """Generate OpenAI-compatible function schema from type hints."""
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        docstring = inspect.getdoc(func) or ""
        param_docs = _parse_docstring_params(docstring)

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "return"):
                continue

            hint = hints.get(param_name, str)
            prop = _json_schema_type(hint)
            prop["description"] = param_docs.get(param_name, param_name)

            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            elif param.default is not None:
                prop["default"] = param.default

            properties[param_name] = prop

        description = docstring.split("\n")[0] if docstring else func.__name__

        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @property
    def schemas(self) -> list[dict[str, Any]]:
        """OpenAI-compatible tool schemas for LLM tool calling."""
        return list(self._schemas)

    @property
    def tool_names(self) -> list[str]:
        """List of registered tool names."""
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """
        Execute a registered tool by name, wrapped in an OTel span.

        The span records: tool name, arguments, response (truncated),
        duration in ms, and success/error status.
        """
        if name not in self._tools:
            raise KeyError(
                f"Unknown tool '{name}'. Available: {', '.join(self._tools)}"
            )

        func = self._tools[name]

        with self._tracer.start_as_current_span(f"tool:{name}") as span:
            span.set_attribute("tool.name", name)
            span.set_attribute("tool.arguments", truncate_json(arguments))

            logger.info("Executing tool: %s(%s)", name, arguments)
            start = time.perf_counter()

            try:
                result = await func(**arguments)
                elapsed_ms = (time.perf_counter() - start) * 1000

                span.set_attribute("tool.success", True)
                span.set_attribute("tool.duration_ms", round(elapsed_ms, 1))
                span.set_attribute("tool.response", truncate_json(result))

                # Log response size for debugging context window issues
                response_chars = len(
                    truncate_json(result, max_chars=999_999)
                )
                span.set_attribute("tool.response_chars", response_chars)
                logger.info(
                    "Tool %s completed in %.0fms (%d chars response)",
                    name,
                    elapsed_ms,
                    response_chars,
                )

                return result

            except TypeError as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                span.set_attribute("tool.success", False)
                span.set_attribute("tool.duration_ms", round(elapsed_ms, 1))
                record_error(span, exc)

                return {
                    "success": False,
                    "error": "INVALID_ARGUMENTS",
                    "message": f"Tool '{name}' received invalid arguments: {exc}",
                    "action": "correct",
                }

            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                span.set_attribute("tool.success", False)
                span.set_attribute("tool.duration_ms", round(elapsed_ms, 1))
                record_error(span, exc)
                logger.exception("Tool '%s' failed", name)

                return {
                    "success": False,
                    "error": "TOOL_EXECUTION_ERROR",
                    "message": f"Tool '{name}' failed: {type(exc).__name__}: {exc}",
                    "action": "retry",
                }