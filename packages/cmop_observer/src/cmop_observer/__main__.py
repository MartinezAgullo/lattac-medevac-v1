"""
Entry point for the CMOP Observer Agent.

Wires all dependencies together and runs the agent.
"""

import asyncio
import logging

from ollama import AsyncClient

from cmop_observer.agent import CMOPObserverAgent
from cmop_observer.api.client import CMOPClient
from cmop_observer.config import Settings
from cmop_observer.prompts import INTERACTIVE_SYSTEM_PROMPT, OBSERVATION_SYSTEM_PROMPT
from cmop_observer.tools import register_basic_tools, register_medical_tools
from latacc_common.tools import ToolRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)


async def run() -> None:
    """Bootstrap and run the CMOP Observer Agent."""
    settings = Settings()

    logger.info("Starting CMOP Observer Agent (model=%s)", settings.model)
    logger.info("CMOP API: %s", settings.api_base)

    async with CMOPClient(settings) as client:
        # Build tool registry
        registry = ToolRegistry()
        register_basic_tools(registry, client)
        register_medical_tools(registry, client)

        logger.info("Registered %d tools: %s", len(registry.tool_names), registry.tool_names)

        # Build LLM client
        llm = AsyncClient(host=settings.ollama_host)

        # Build agent
        agent = CMOPObserverAgent(
            client=client,
            llm=llm,
            tools=registry,
            settings=settings,
        )

        # Load schema for dynamic awareness
        await agent.load_schema()

        # Initial observation
        print("\n🔍 Starting CMOP observation...\n")
        analysis = await agent.run_loop(
            user_prompt=(
                "Analyze the current CMOP state. "
                "What is the medical situation? "
                "Identify critical priorities and evacuation recommendations."
            ),
            system_prompt=OBSERVATION_SYSTEM_PROMPT,
        )

        print("\n" + "=" * 60)
        print("📊 INITIAL CMOP ANALYSIS")
        print("=" * 60)
        print(analysis)
        print("=" * 60 + "\n")

        # Interactive mode
        await agent.interactive_session(INTERACTIVE_SYSTEM_PROMPT)


def main() -> None:
    """Sync entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
