"""
latacc_common/models/entities.py

Pydantic models for CMOP map entities and medical records.
Field names and aliases match the JSON shape returned by the
cmop_map API (entity.js baseSelect).
"""

from datetime import datetime

from pydantic import BaseModel, Field

from latacc_common.models.enums import (
    Alliance,
    CasualtyStatus,
    EvacPriority,
    EvacStage,
    TriageColor,
)


class DestinationFacility(BaseModel):
    """Resolved FK reference to the destination medical facility."""

    id: int
    name: str = Field(alias="nombre")

    model_config = {"populate_by_name": True}


class MedicalRecord(BaseModel):
    """
    Medical details attached to a casualty entity.

    Mirrors the ``medical`` JSONB object built by entity.js baseSelect().
    All fields are optional — ``UNKNOWN``/``null`` is the default state.
    """

    # Triage & injury
    triage_color: TriageColor = TriageColor.UNKNOWN
    casualty_status: CasualtyStatus = CasualtyStatus.UNKNOWN
    injury_mechanism: str | None = None
    primary_injury: str | None = None
    vital_signs: list[dict] | None = None
    prehospital_treatment: str | None = None

    # Evacuation management
    evac_priority: EvacPriority = EvacPriority.UNKNOWN
    evac_stage: EvacStage = EvacStage.UNKNOWN
    destination_facility: DestinationFacility | None = None

    # 9-Line MEDEVAC request (NATO STANAG format, stored as JSONB)
    nine_line_data: dict | None = None

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"extra": "ignore"}


class Entity(BaseModel):
    """
    A CMOP map entity (military unit, casualty, facility, etc.).

    Field aliases map the Spanish-language API names to English
    Python attributes. ``populate_by_name=True`` allows construction
    with either name.
    """

    id: int
    name: str = Field(alias="nombre")
    description: str | None = Field(default=None, alias="descripcion")
    category: str = Field(alias="categoria")
    country: str | None = None
    alliance: Alliance = Alliance.UNKNOWN
    identified_element: str | None = Field(
        default=None, alias="elemento_identificado"
    )
    active: bool = Field(default=True, alias="activo")
    element_type: str | None = Field(default=None, alias="tipo_elemento")
    priority: int = Field(default=0, alias="prioridad")
    observations: str | None = Field(default=None, alias="observaciones")
    altitude: float | None = Field(default=None, alias="altitud")
    latitude: float = Field(alias="latitud")
    longitude: float = Field(alias="longitud")
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Medical record (null for non-casualty entities)
    medical: MedicalRecord | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}
