"""
cmop_observer/api/client.py

Async HTTP client for the CMOP Map REST API.
Maintains a single httpx.AsyncClient for connection pooling.
All methods return ApiResponse with structured error signals.
"""

import logging
from typing import Any

import httpx

from cmop_observer.config import Settings
from latacc_common.models import ApiResponse, ErrorAction

logger = logging.getLogger(__name__)


class CMOPClient:
    """
    Async client for the CMOP Map REST API.

    Usage::

        async with CMOPClient(settings) as client:
            result = await client.get_entities()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    # -- Lifecycle (async context manager) ----------------------------------

    async def __aenter__(self) -> "CMOPClient":
        self._http = httpx.AsyncClient(
            base_url=self._settings.api_base,
            timeout=self._settings.request_timeout,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # -- Internal helpers ---------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> ApiResponse:
        """
        Execute GET request with structured error handling.

        Returns ApiResponse with ErrorAction signal so the LLM
        can decide whether to retry, correct, or incorporate info.
        """
        if not self._http:
            raise RuntimeError("CMOPClient not initialized. Use 'async with'.")

        try:
            resp = await self._http.get(path, params=params)

            if resp.status_code == 404:
                return ApiResponse(
                    success=False,
                    error="NOT_FOUND",
                    message=f"Resource not found: {path}",
                    action=ErrorAction.INFORM,
                )

            if resp.status_code >= 500:
                return ApiResponse(
                    success=False,
                    error="SERVER_ERROR",
                    message=f"CMOP API server error (HTTP {resp.status_code})",
                    action=ErrorAction.RETRY,
                    retry_after_seconds=5,
                )

            if resp.status_code >= 400:
                return ApiResponse(
                    success=False,
                    error="CLIENT_ERROR",
                    message=f"Invalid request (HTTP {resp.status_code}): {resp.text[:200]}",
                    action=ErrorAction.CORRECT,
                )

            try:
                data = resp.json()
                return ApiResponse(success=True, data=data.get("data", data))
            except Exception as exc:
                return ApiResponse(
                    success=False,
                    error="INVALID_JSON",
                    message=f"Failed to parse response: {exc}",
                    action=ErrorAction.RETRY,
                )

        except httpx.TimeoutException:
            return ApiResponse(
                success=False,
                error="TIMEOUT",
                message=f"Request timeout after {self._settings.request_timeout}s",
                action=ErrorAction.RETRY,
                retry_after_seconds=3,
            )

        except httpx.ConnectError:
            return ApiResponse(
                success=False,
                error="CONNECTION_REFUSED",
                message=(
                    f"Cannot connect to CMOP API at {self._settings.api_base}. "
                    "Is the server running?"
                ),
                action=ErrorAction.RETRY,
                retry_after_seconds=10,
            )

        except httpx.NetworkError as exc:
            return ApiResponse(
                success=False,
                error="NETWORK_ERROR",
                message=f"Network error: {exc}",
                action=ErrorAction.RETRY,
            )

    # -- Entity endpoints ---------------------------------------------------

    async def get_entities(self) -> ApiResponse[list[dict]]:
        """GET /api/entities — all entities."""
        return await self._get("/api/entities")

    async def get_entity(self, entity_id: int) -> ApiResponse[dict]:
        """GET /api/entities/:id — single entity by ID."""
        return await self._get(f"/api/entities/{entity_id}")

    async def get_entities_by_category(self, category: str) -> ApiResponse[list[dict]]:
        """GET /api/entities/categoria/:c — filter by category."""
        return await self._get(f"/api/entities/categoria/{category}")

    async def get_nearby_entities(
        self,
        longitude: float,
        latitude: float,
        radius_m: int = 5000,
    ) -> ApiResponse[list[dict]]:
        """GET /api/entities/cerca/:lng/:lat — spatial radius query."""
        return await self._get(
            f"/api/entities/cerca/{longitude}/{latitude}",
            params={"radio": radius_m},
        )

    # -- Medical endpoints --------------------------------------------------

    async def get_casualties(self) -> ApiResponse[list[dict]]:
        """GET /api/medical/casualties — all entities with medical records."""
        return await self._get("/api/medical/casualties")

    async def get_casualties_by_triage(self, color: str) -> ApiResponse[list[dict]]:
        """GET /api/medical/triage/:color — filter by triage color."""
        return await self._get(f"/api/medical/triage/{color}")

    async def get_casualties_by_evac_stage(self, stage: str) -> ApiResponse[list[dict]]:
        """GET /api/medical/evac-stage/:stage — filter by evac stage."""
        return await self._get(f"/api/medical/evac-stage/{stage}")

    async def get_nine_line(self, entity_id: int) -> ApiResponse[dict]:
        """GET /api/medical/:entity_id/nine-line — 9-Line MEDEVAC data."""
        return await self._get(f"/api/medical/{entity_id}/nine-line")

    # -- Schema / Scenarios -------------------------------------------------

    async def get_schema(self) -> ApiResponse[dict]:
        """GET /api/schema — categories, enums, subtypes."""
        return await self._get("/api/schema")

    async def get_scenarios(self) -> ApiResponse[list[dict]]:
        """GET /api/scenarios — available scenarios."""
        return await self._get("/api/scenarios")
