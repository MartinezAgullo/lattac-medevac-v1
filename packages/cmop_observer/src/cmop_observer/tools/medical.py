"""
cmop_observer/tools/medical.py

Medical domain tools with NATO AJMedP-2 doctrine logic.
Composes basic API calls with deterministic domain logic
so the LLM doesn't have to do math or complex reasoning.
"""

from datetime import datetime, timezone

from cmop_observer.api.client import CMOPClient
from cmop_observer.utils import estimate_ground_eta, haversine_distance
from latacc_common.models.enums import FacilityRole
from latacc_common.tools import ToolRegistry


def register_medical_tools(registry: ToolRegistry, client: CMOPClient) -> None:
    """Register medical domain analysis tools."""

    @registry.register
    async def find_nearest_facility_by_role(
        casualty_lat: float,
        casualty_lng: float,
        min_role: int = 1,
        max_distance_m: int = 50000,
    ) -> dict:
        """Find nearest medical facility with minimum role capability.

        Args:
            casualty_lat: Casualty latitude (WGS84).
            casualty_lng: Casualty longitude (WGS84).
            min_role: Minimum role required (1=aid post, 2=surgical, 3=field hospital, 4=definitive).
            max_distance_m: Maximum search radius in meters (default 50000).
        """
        nearby = await client.get_nearby_entities(
            casualty_lng, casualty_lat, max_distance_m
        )
        if not nearby.success:
            return nearby.model_dump(exclude_none=True)

        entities = nearby.data or []
        facilities = [e for e in entities if e.get("categoria") == "medical_facility"]

        if not facilities:
            return {
                "success": True,
                "data": None,
                "message": f"No medical facilities found within {max_distance_m}m",
                "action": "inform",
            }

        eligible = []
        for f in facilities:
            tipo = f.get("tipo_elemento", "")
            try:
                role = FacilityRole(tipo)
                role_level = role.level
            except ValueError:
                role_level = 0

            if role_level >= min_role:
                dist = haversine_distance(
                    casualty_lng, casualty_lat,
                    f["longitud"], f["latitud"],
                )
                eligible.append({
                    "id": f["id"],
                    "name": f.get("nombre"),
                    "role": tipo,
                    "role_level": role_level,
                    "distance_m": int(dist),
                    "eta_minutes": estimate_ground_eta(dist),
                    "latitude": f["latitud"],
                    "longitude": f["longitud"],
                    "country": f.get("country"),
                    "alliance": f.get("alliance"),
                })

        if not eligible:
            return {
                "success": True,
                "data": None,
                "message": f"No Role {min_role}+ facilities within {max_distance_m}m",
                "action": "inform",
            }

        eligible.sort(key=lambda x: x["distance_m"])
        return {
            "success": True,
            "data": {
                "nearest": eligible[0],
                "alternatives": eligible[1:4],
            },
        }

    @registry.register
    async def check_10_1_2_compliance(entity_id: int) -> dict:
        """Check if casualty evacuation meets NATO 10-1-2 timeline (10min first aid, 1hr DCR, 2hr surgery).

        Args:
            entity_id: Casualty entity ID.
        """
        result = await client.get_entity(entity_id)
        if not result.success:
            return result.model_dump(exclude_none=True)

        entity = result.data
        if not entity:
            return {
                "success": False,
                "error": "NOT_FOUND",
                "message": f"Entity {entity_id} not found",
                "action": "inform",
            }

        medical = entity.get("medical")
        if not medical:
            return {
                "success": False,
                "error": "NOT_CASUALTY",
                "message": f"Entity {entity_id} has no medical record",
                "action": "inform",
            }

        # Parse injury timestamp
        created_at_str = entity.get("created_at")
        if not created_at_str:
            return {
                "success": False,
                "error": "NO_TIMESTAMP",
                "message": "Entity has no created_at timestamp",
                "action": "inform",
            }

        try:
            injury_time = datetime.fromisoformat(
                str(created_at_str).replace("Z", "+00:00")
            )
        except (ValueError, TypeError) as exc:
            return {
                "success": False,
                "error": "INVALID_TIMESTAMP",
                "message": f"Cannot parse timestamp: {exc}",
                "action": "inform",
            }

        now = datetime.now(timezone.utc)
        elapsed_minutes = int((now - injury_time).total_seconds() / 60)

        triage = medical.get("triage_color", "UNKNOWN")
        evac_stage = medical.get("evac_stage", "unknown")
        casualty_status = medical.get("casualty_status", "UNKNOWN")
        evac_priority = medical.get("evac_priority", "UNKNOWN")
        is_red = triage == "RED"

        # Skip timeline check for KIA
        if casualty_status == "KIA":
            return {
                "success": True,
                "data": {
                    "entity_id": entity_id,
                    "name": entity.get("nombre"),
                    "triage_color": triage,
                    "casualty_status": "KIA",
                    "message": "Casualty is KIA — timeline check not applicable.",
                },
            }

        # Timeline assessment
        timeline = {}

        # 10-minute rule (first aid at POI)
        if elapsed_minutes <= 10:
            timeline["first_aid_10min"] = "COMPLIANT"
        else:
            timeline["first_aid_10min"] = "VIOLATED" if is_red else "DELAYED"

        # 1-hour rule (DCR)
        if elapsed_minutes <= 60:
            timeline["dcr_1hour"] = "COMPLIANT"
        elif evac_stage in ("in_transit", "delivered"):
            timeline["dcr_1hour"] = "COMPLIANT (en route or delivered)"
        else:
            timeline["dcr_1hour"] = "VIOLATED" if is_red else "AT_RISK"

        # 2-hour rule (DCS)
        if elapsed_minutes <= 120:
            timeline["dcs_2hour"] = "COMPLIANT"
        elif evac_stage == "delivered":
            timeline["dcs_2hour"] = "COMPLIANT (delivered to facility)"
        else:
            timeline["dcs_2hour"] = "VIOLATED" if is_red else "AT_RISK"

        # Recommendations
        recommendations = []
        if is_red and evac_stage == "at_poi" and elapsed_minutes > 30:
            recommendations.append(
                "URGENT: RED casualty still at POI after 30min — "
                "immediate forward MEDEVAC required"
            )
        if is_red and elapsed_minutes > 60 and evac_stage != "delivered":
            recommendations.append(
                "CRITICAL: RED casualty exceeds 1-hour DCR timeline — "
                "prioritize immediate surgical evacuation"
            )
        if triage in ("RED", "YELLOW") and elapsed_minutes > 120 and evac_stage != "delivered":
            recommendations.append(
                "VIOLATION: 2-hour DCS timeline exceeded — "
                "escalate to MASCAL protocols"
            )
        if evac_priority == "URGENT" and evac_stage == "at_poi" and elapsed_minutes > 15:
            recommendations.append(
                "URGENT priority casualty still at POI — "
                "coordinate immediate evacuation asset"
            )

        # Destination facility info
        dest_facility = medical.get("destination_facility")

        return {
            "success": True,
            "data": {
                "entity_id": entity_id,
                "name": entity.get("nombre"),
                "triage_color": triage,
                "casualty_status": casualty_status,
                "evac_stage": evac_stage,
                "evac_priority": evac_priority,
                "time_since_injury_minutes": elapsed_minutes,
                "injury_timestamp": created_at_str,
                "destination_facility": dest_facility,
                "timeline_status": timeline,
                "recommendations": recommendations or ["Timeline compliant"],
            },
        }

    @registry.register
    async def get_mascal_summary() -> dict:
        """Get MASCAL situation overview: casualties by triage/stage/status, facilities, risk assessment."""
        casualties_resp = await client.get_casualties()
        if not casualties_resp.success:
            return casualties_resp.model_dump(exclude_none=True)

        casualties = casualties_resp.data or []

        facilities_resp = await client.get_entities_by_category("medical_facility")
        if not facilities_resp.success:
            return facilities_resp.model_dump(exclude_none=True)

        facilities = facilities_resp.data or []

        # Aggregate triage, evac stage, and casualty status
        triage_counts: dict[str, int] = {
            "RED": 0, "YELLOW": 0, "GREEN": 0, "BLUE": 0, "BLACK": 0, "UNKNOWN": 0,
        }
        evac_counts: dict[str, int] = {
            "at_poi": 0, "in_transit": 0, "delivered": 0, "unknown": 0,
        }
        status_counts: dict[str, int] = {"WIA": 0, "KIA": 0, "UNKNOWN": 0}
        critical_at_poi: list[dict] = []

        for c in casualties:
            med = c.get("medical", {})
            triage = med.get("triage_color", "UNKNOWN")
            evac = med.get("evac_stage", "unknown")
            status = med.get("casualty_status", "UNKNOWN")

            triage_counts[triage] = triage_counts.get(triage, 0) + 1
            evac_counts[evac] = evac_counts.get(evac, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1

            if triage == "RED" and evac == "at_poi":
                critical_at_poi.append({
                    "id": c["id"],
                    "name": c.get("nombre"),
                    "latitude": c.get("latitud"),
                    "longitude": c.get("longitud"),
                    "evac_priority": med.get("evac_priority", "UNKNOWN"),
                    "injury_mechanism": med.get("injury_mechanism"),
                })

        # Facility breakdown
        facility_counts: dict[str, int] = {}
        for f in facilities:
            role = f.get("tipo_elemento", "unknown")
            facility_counts[role] = facility_counts.get(role, 0) + 1

        # MASCAL risk assessment
        red = triage_counts["RED"]
        total = len(casualties)

        if red >= 10 or total >= 30:
            mascal_status = "MASCAL_DECLARED"
        elif red >= 5 or total >= 15:
            mascal_status = "MASCAL_WARNING"
        else:
            mascal_status = "NORMAL"

        risk_map = {
            "MASCAL_DECLARED": "HIGH",
            "MASCAL_WARNING": "MODERATE",
            "NORMAL": "LOW",
        }

        return {
            "success": True,
            "data": {
                "total_casualties": total,
                "triage_distribution": triage_counts,
                "evac_stage_distribution": evac_counts,
                "casualty_status_distribution": status_counts,
                "critical_at_poi_count": len(critical_at_poi),
                "critical_at_poi": critical_at_poi[:5],
                "facilities_available": facility_counts,
                "total_facilities": len(facilities),
                "mascal_status": mascal_status,
                "assessment": {
                    "RED_casualties": red,
                    "YELLOW_casualties": triage_counts["YELLOW"],
                    "KIA_count": status_counts["KIA"],
                    "immediate_evac_needed": len(critical_at_poi),
                    "overwhelmed_risk": risk_map[mascal_status],
                },
            },
        }
