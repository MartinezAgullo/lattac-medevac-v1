"""
latacc_common/models/enums.py

Domain enumerations shared across LATACC agents.
Mirrors the PostgreSQL enums defined in cmop_map's init-db.js.
"""

from enum import StrEnum


class TriageColor(StrEnum):
    """NATO triage classification colors (AJMedP-7 / STANAG 2879)."""

    RED = "RED"          # T1 — Immediate (life-threatening)
    YELLOW = "YELLOW"    # T2 — Urgent (serious but stable)
    GREEN = "GREEN"      # T3 — Minimal (walking wounded)
    BLUE = "BLUE"        # T4 — Expectant (likely to die in MASCAL)
    BLACK = "BLACK"      # Deceased
    UNKNOWN = "UNKNOWN"


class EvacStage(StrEnum):
    """Current evacuation stage of a casualty."""

    AT_POI = "at_poi"          # At point of injury
    IN_TRANSIT = "in_transit"  # Being evacuated
    DELIVERED = "delivered"    # Arrived at facility
    UNKNOWN = "unknown"


class EvacPriority(StrEnum):
    """MEDEVAC evacuation priority (NATO / TCCC)."""

    URGENT = "URGENT"      # Life-threatening, needs care within 1h
    PRIORITY = "PRIORITY"  # Serious but stable, within 4h
    ROUTINE = "ROUTINE"    # Stable, within 24h
    UNKNOWN = "UNKNOWN"


class CasualtyStatus(StrEnum):
    """Casualty status classification."""

    WIA = "WIA"          # Wounded in action
    KIA = "KIA"          # Killed in action
    UNKNOWN = "UNKNOWN"


class Alliance(StrEnum):
    """Entity allegiance/affiliation."""

    FRIENDLY = "friendly"
    HOSTILE = "hostile"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class FacilityRole(StrEnum):
    """NATO medical facility role levels (AJMedP-2)."""

    ROLE_1 = "medical_role_1"
    ROLE_2 = "medical_role_2"
    ROLE_2_BASIC = "medical_role_2basic"
    ROLE_2_ENHANCED = "medical_role_2enhanced"
    ROLE_3 = "medical_role_3"
    ROLE_4 = "medical_role_4"
    MULTINATIONAL = "medical_facility_multinational"

    @property
    def level(self) -> int:
        """Numeric role level for comparison and sorting."""
        mapping = {
            "medical_role_1": 1,
            "medical_role_2": 2,
            "medical_role_2basic": 2,
            "medical_role_2enhanced": 2,
            "medical_role_3": 3,
            "medical_role_4": 4,
            "medical_facility_multinational": 3,
        }
        return mapping.get(self.value, 0)
