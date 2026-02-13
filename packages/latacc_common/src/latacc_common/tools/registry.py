"""
Tool registry with automatic OpenAI-compatible schema generation.

Eliminates the need to manually maintain JSON schemas alongside
Python function definitions. Schemas are derived from type hints
and docstrings at registration time.
"""

import inspect
import logging
from enum import StrEnum
from typing import Any, Callable, get_type_hints

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
    # Handle StrEnum subclasses → string with enum values
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
                # Left the Args section
                break
            if ":" in stripped:
                name, _, desc = stripped.lstrip("- ").partition(":")
                params[name.strip()] = desc.strip()

    return params


class ToolRegistry:
    """
    Central registry for agent tools with auto-schema generation.

    Usage:
        registry = ToolRegistry()

        @registry.register
        async def get_entity_by_id(entity_id: int) -> dict:
            '''Get single entity by numeric ID.'''
            ...

        # Schemas are auto-generated for Ollama/OpenAI tool calling
        schemas = registry.schemas
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}
        self._schemas: list[dict[str, Any]] = []

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

        # Use first line of docstring as tool description
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
        Execute a registered tool by name.

        Args:
            name: Tool function name.
            arguments: Keyword arguments to pass to the tool.

        Returns:
            Tool result (typically an ApiResponse-compatible dict).

        Raises:
            KeyError: If tool name is not registered.
        """
        if name not in self._tools:
            raise KeyError(
                f"Unknown tool '{name}'. Available: {', '.join(self._tools)}"
            )

        func = self._tools[name]
        logger.info("Executing tool: %s(%s)", name, arguments)

        try:
            return await func(**arguments)
        except TypeError as exc:
            # Bad arguments from the LLM
            return {
                "success": False,
                "error": "INVALID_ARGUMENTS",
                "message": f"Tool '{name}' received invalid arguments: {exc}",
                "action": "correct",
            }
        except Exception as exc:
            logger.exception("Tool '%s' failed", name)
            return {
                "success": False,
                "error": "TOOL_EXECUTION_ERROR",
                "message": f"Tool '{name}' failed: {type(exc).__name__}: {exc}",
                "action": "retry",
            }
