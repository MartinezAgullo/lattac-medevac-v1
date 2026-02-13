"""
CMOP Observer Agent — lean orchestrator.

Follows the Observe → Think → Act → Reflect loop.
All dependencies are injected; the agent owns only the reasoning loop.
"""

import json
import logging
from typing import Any

from ollama import AsyncClient

from cmop_observer.api.client import CMOPClient
from cmop_observer.config import Settings
from latacc_common.tools import ToolRegistry

logger = logging.getLogger(__name__)


class CMOPObserverAgent:
    """
    MEDEVAC observer agent with tool calling capabilities.

    Dependencies are injected via constructor — no hardcoded URLs,
    clients, or model names.
    """

    def __init__(
        self,
        client: CMOPClient,
        llm: AsyncClient,
        tools: ToolRegistry,
        settings: Settings,
    ) -> None:
        self._client = client
        self._llm = llm
        self._tools = tools
        self._settings = settings
        self._schema_cache: dict = {}

        # Register the `done` signal tool
        self._done_result: str | None = None
        self._register_done_tool()

    def _register_done_tool(self) -> None:
        """Register a 'done' tool the agent calls to signal completion."""

        @self._tools.register
        async def done(summary: str) -> dict:
            """Signal that analysis is complete and provide the final summary.

            Args:
                summary: The final analysis summary to present to the user.
            """
            self._done_result = summary
            return {"success": True, "message": "Analysis complete."}

    async def load_schema(self) -> None:
        """Load CMOP schema at startup for dynamic category awareness."""
        logger.info("Loading CMOP schema...")
        result = await self._client.get_schema()

        if result.success and result.data:
            self._schema_cache = result.data
            categories = result.data.get("categories", [])
            logger.info("Schema loaded: %d categories available", len(categories))
        else:
            logger.warning("Schema load failed: %s", result.message)

    async def run_loop(
        self,
        user_prompt: str,
        system_prompt: str,
    ) -> str:
        """
        Execute the agent reasoning loop.

        Observe → Think → Act → Reflect, until the agent calls `done`
        or hits the iteration limit.

        Args:
            user_prompt: The initial user message or task.
            system_prompt: System prompt defining agent behaviour.

        Returns:
            The agent's final analysis text.
        """
        self._done_result = None
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for iteration in range(1, self._settings.max_iterations + 1):
            logger.debug("Iteration %d/%d", iteration, self._settings.max_iterations)

            # Think — LLM call
            response = await self._llm.chat(
                model=self._settings.model,
                messages=messages,
                tools=self._tools.schemas,
            )

            message = response["message"]
            messages.append(message)

            # No tool calls → agent finished (implicit done)
            if not message.get("tool_calls"):
                return message.get("content", "")

            # Act — execute tool calls
            for tool_call in message["tool_calls"]:
                name = tool_call["function"]["name"]
                args = tool_call["function"]["arguments"]

                logger.info("Tool call: %s(%s)", name, json.dumps(args, ensure_ascii=False))

                result = await self._tools.execute(name, args)

                # Reflect — add result to history
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

                # Check if agent signalled done
                if self._done_result is not None:
                    logger.info("Agent signalled done at iteration %d", iteration)
                    return self._done_result

        logger.warning("Agent exceeded max iterations (%d)", self._settings.max_iterations)
        return "⚠️ Analysis incomplete — agent exceeded iteration limit."

    async def interactive_session(self, system_prompt: str) -> None:
        """
        Interactive Q&A loop for terminal usage.

        Maintains conversation history across questions.
        """
        print("\n" + "=" * 60)
        print("🏥 CMOP Observer Agent — Interactive Mode")
        print("=" * 60)
        print("Ask questions about the CMOP state. Type 'quit' to exit.\n")

        conversation: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Exiting.")
                break

            if user_input.lower() in ("quit", "exit", "q"):
                print("👋 Exiting interactive mode.")
                break

            if not user_input:
                continue

            conversation.append({"role": "user", "content": user_input})

            # Reasoning loop for this turn
            for _ in range(self._settings.max_iterations):
                response = await self._llm.chat(
                    model=self._settings.model,
                    messages=conversation,
                    tools=self._tools.schemas,
                )

                message = response["message"]
                conversation.append(message)

                if not message.get("tool_calls"):
                    print(f"\n🤖 Agent: {message.get('content', '')}\n")
                    break

                for tool_call in message["tool_calls"]:
                    name = tool_call["function"]["name"]
                    args = tool_call["function"]["arguments"]

                    print(f"  [calling {name}...]")

                    result = await self._tools.execute(name, args)
                    conversation.append({
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
