"""
cmop_observer/tools/basic.py

Basic read-only tools for querying the CMOP API.
Schemas are auto-generated from type hints and docstrings.
"""

from cmop_observer.api.client import CMOPClient
from latacc_common.tools import ToolRegistry


def register_basic_tools(registry: ToolRegistry, client: CMOPClient) -> None:
    """Register all basic CMOP API query tools."""

    @registry.register
    async def get_all_entities() -> dict:
        """Get all entities from CMOP map (military units, casualties, facilities)."""
        result = await client.get_entities()
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_entity_by_id(entity_id: int) -> dict:
        """Get single entity by numeric ID with full medical details."""
        result = await client.get_entity(entity_id)
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_entities_by_category(category: str) -> dict:
        """Get entities filtered by category.

        Args:
            category: Entity category (infantry, armoured, casualty, medical_facility, medevac_unit, etc.).
        """
        result = await client.get_entities_by_category(category)
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_casualties() -> dict:
        """Get all casualties (entities with medical records) including triage, evac stage, vital signs, and 9-Line data."""
        result = await client.get_casualties()
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_casualties_by_triage(color: str) -> dict:
        """Get casualties filtered by triage color.

        Args:
            color: Triage color — RED (T1 immediate), YELLOW (T2 urgent), GREEN (T3 minimal), BLUE (T4 expectant), BLACK (deceased), UNKNOWN.
        """
        result = await client.get_casualties_by_triage(color)
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_casualties_by_evac_stage(stage: str) -> dict:
        """Get casualties filtered by evacuation stage.

        Args:
            stage: Evacuation stage — at_poi (point of injury), in_transit (being evacuated), delivered (at facility), unknown.
        """
        result = await client.get_casualties_by_evac_stage(stage)
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_nearby_entities(
        longitude: float, latitude: float, radius_m: int = 5000
    ) -> dict:
        """Find entities within radius of coordinates.

        Args:
            longitude: WGS84 longitude.
            latitude: WGS84 latitude.
            radius_m: Search radius in meters (default 5000).
        """
        result = await client.get_nearby_entities(longitude, latitude, radius_m)
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_nine_line(entity_id: int) -> dict:
        """Get the 9-Line MEDEVAC request data for a specific casualty.

        Args:
            entity_id: Casualty entity ID.
        """
        result = await client.get_nine_line(entity_id)
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_schema() -> dict:
        """Get CMOP schema with valid categories, triage colors, evac stages, facility roles, and 9-Line MEDEVAC format."""
        result = await client.get_schema()
        return result.model_dump(exclude_none=True)

    @registry.register
    async def get_available_scenarios() -> dict:
        """List available scenarios that can be loaded."""
        result = await client.get_scenarios()
        return result.model_dump(exclude_none=True)
