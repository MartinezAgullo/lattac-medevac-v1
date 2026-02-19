"""
cmop_observer/agent.py

CMOP Observer Agent — lean orchestrator with unified session.
The agent maintains a single message history across observation
and interactive modes, so context from the initial analysis is
available during Q&A.
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

    Maintains a single message history for the entire session so that
    the interactive mode retains context from the initial observation.
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
        self._messages: list[dict[str, Any]] = []
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

    def init_session(self, system_prompt: str) -> None:
        """Initialise the message history with the system prompt."""
        self._messages = [{"role": "system", "content": system_prompt}]

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

    async def _run_tool_loop(self) -> str:
        """
        Execute the Think → Act → Reflect loop until the agent
        stops calling tools or hits the iteration limit.

        Returns:
            The agent's final text response.
        """
        self._done_result = None

        for iteration in range(1, self._settings.max_iterations + 1):
            logger.debug("Iteration %d/%d", iteration, self._settings.max_iterations)

            # Think — LLM call
            response = await self._llm.chat(
                model=self._settings.model,
                messages=self._messages,
                tools=self._tools.schemas,
            )

            message = response["message"]
            self._messages.append(message)

            # No tool calls → agent finished (implicit done)
            if not message.get("tool_calls"):
                return message.get("content", "")

            # Act — execute each tool call
            for tool_call in message["tool_calls"]:
                name = tool_call["function"]["name"]
                args = tool_call["function"]["arguments"]

                logger.info(
                    "Tool call: %s(%s)",
                    name,
                    json.dumps(args, ensure_ascii=False),
                )

                result = await self._tools.execute(name, args)

                # Reflect — add result to history
                self._messages.append({
                    "role": "tool",
                    "content": json.dumps(
                        result, ensure_ascii=False, default=str
                    ),
                })

                # Check explicit done signal
                if self._done_result is not None:
                    logger.info("Agent signalled done at iteration %d", iteration)
                    return self._done_result

        logger.warning(
            "Agent exceeded max iterations (%d)", self._settings.max_iterations
        )
        return "⚠️ Analysis incomplete — agent exceeded iteration limit."

    async def observe(self, task: str) -> str:
        """
        Run an observation task (e.g. initial CMOP analysis).

        The task is added to the shared message history so that
        the interactive session retains full context.

        Args:
            task: The observation task prompt.

        Returns:
            The agent's analysis text.
        """
        self._messages.append({"role": "user", "content": task})
        result = await self._run_tool_loop()
        # The result is already in messages via the assistant message
        return result

    async def interactive_session(self) -> None:
        """
        Interactive Q&A loop for terminal usage.

        Uses the same message history as observe(), so the agent
        remembers the initial analysis and all tool results.
        """
        print("\n" + "=" * 60)
        print("🏥 CMOP Observer Agent — Interactive Mode")
        print("=" * 60)
        print("Ask questions about the CMOP state. Type 'quit' to exit.")
        print("The agent remembers the initial analysis.\n")

        while True:
            try:
                user_input = input("👨🏻‍⚕️ You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Exiting.")
                break

            if user_input.lower() in ("quit", "exit", "q"):
                print("👋 Exiting interactive mode.")
                break

            if not user_input:
                continue

            self._messages.append({"role": "user", "content": user_input})

            response = await self._run_tool_loop()
            print(f"\n🤖 Agent: {response}\n")