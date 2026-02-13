---
name: evacuation-prioritization
description: >
  Ranks casualties by evacuation priority using NATO AJMedP-2 doctrine.
  Composes API queries with deterministic haversine distance calculations
  and 10-1-2 timeline compliance checks to produce a pre-digested
  evacuation priority list. Reduces LLM reasoning errors by handling
  all math and ranking logic internally.
---

# Evacuation Prioritization Skill

## When to use this skill

Use this skill when the agent needs to determine **which casualties
should be evacuated first** and **to which facility**. Instead of the
LLM chaining multiple tool calls and doing distance/time math (risky),
this skill produces a single ranked list.

## What it does

1. Fetches all RED and YELLOW casualties at POI.
2. For each casualty, checks 10-1-2 timeline compliance.
3. Finds the nearest appropriate facility (Role 2+ for RED, Role 1+ for YELLOW).
4. Computes haversine distance and ground ETA.
5. Ranks by composite urgency score:
   - Triage severity (RED > YELLOW)
   - Timeline violation severity
   - Time since injury
   - Distance to nearest facility

## Output format

Returns a ranked list of evacuation recommendations, each containing:
- Casualty ID, name, triage color, coordinates
- Time since injury (minutes)
- Timeline compliance status
- Recommended facility (name, role, distance, ETA)
- Urgency score (higher = more urgent)

## Limitations

- Uses ground ambulance speed (60 km/h) for ETA. Does not account
  for terrain, helicopter MEDEVAC, or road conditions.
- MASCAL threshold detection is basic (count-based, not capacity-aware).
- Facility capacity/bed availability is not tracked by the current API.
