"""
latacc_common/models/__init__.py

Domain models shared across all LATACC agents.
"""

from latacc_common.models.api_response import ApiResponse, ErrorAction
from latacc_common.models.entities import (
    DestinationFacility,
    Entity,
    MedicalRecord,
)
from latacc_common.models.enums import (
    Alliance,
    CasualtyStatus,
    EvacPriority,
    EvacStage,
    FacilityRole,
    TriageColor,
)

__all__ = [
    "Alliance",
    "ApiResponse",
    "CasualtyStatus",
    "DestinationFacility",
    "Entity",
    "ErrorAction",
    "EvacPriority",
    "EvacStage",
    "FacilityRole",
    "MedicalRecord",
    "TriageColor",
]
