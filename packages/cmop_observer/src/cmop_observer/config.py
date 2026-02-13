"""Observer agent configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuration for the CMOP Observer Agent.

    All values can be overridden via environment variables
    with the ``CMOP_`` prefix. Example::

        CMOP_MODEL=llama3:70b CMOP_API_BASE=http://10.0.0.5:3000 cmop-observer
    """

    # CMOP API connection
    api_base: str = "http://localhost:3000"
    request_timeout: float = 30.0

    # Ollama / LLM
    model: str = "qwen2.5:14b-instruct"
    ollama_host: str = "http://localhost:11434"

    # Agent behaviour
    max_iterations: int = 15

    model_config = {"env_prefix": "CMOP_"}
