"""
Medical Agent — assesses medical demand, requests ambulances and medical teams.
"""
import math
from typing import List, Dict, Tuple
from models import AffectedZone, ZoneAllocation, AgentStatus, Priority


class MedicalAgent:
    NAME = "Medical"

    def __init__(self, engine):
        self.engine = engine

    def analyze(self, zones: List[AffectedZone]) -> Dict[str, Dict]:
        """
        Assess medical demand per zone.
        Returns request dict: {zone_id: {ambulances, medical_teams, medical_kits, reason}}
        """
        self.engine.set_agent_status(self.NAME, AgentStatus.ANALYZING, "Assessing critical patient load")

        requests = {}
        for zone in zones:
            # Ambulance need: 1 per 5 critical patients, min 1
            amb_need = max(1, math.ceil(zone.critical_patients / 5))
            # Medical team need: 1 per 8 critical patients, min 1
            team_need = max(1, math.ceil(zone.critical_patients / 8))
            # Medical kits: 10 per critical + 5 per injured
            kits = zone.critical_patients * 10 + zone.injured_people * 5

            reason = (
                f"{zone.zone_name} requires {amb_need} ambulances: "
                f"{zone.critical_patients} critical patients estimated "
                f"(ratio: 1 ambulance per 5 critical). "
                f"Priority: {zone.priority.value}."
            )

            requests[zone.zone_id] = {
                "ambulances": amb_need,
                "medical_teams": team_need,
                "medical_kits": kits,
                "reason": reason,
                "priority": zone.priority,
                "critical_patients": zone.critical_patients,
            }

        total_amb = sum(r["ambulances"] for r in requests.values())
        total_teams = sum(r["medical_teams"] for r in requests.values())

        self.engine.add_agent_event(
            self.NAME, "Medical demand assessment complete",
            request=f"Total ambulances needed: {total_amb} | Medical teams needed: {total_teams}",
            reason=f"Across {len(zones)} zones with "
                   f"{sum(z.critical_patients for z in zones)} critical patients total"
        )

        self.engine.set_agent_status(
            self.NAME, AgentStatus.REQUESTING,
            f"Requesting {total_amb} ambulances, {total_teams} medical teams"
        )
        return requests

    def identify_shortages(self, requests: Dict, available_ambulances: int, available_teams: int):
        """Log shortage alerts."""
        total_amb = sum(r["ambulances"] for r in requests.values())
        total_teams = sum(r["medical_teams"] for r in requests.values())

        if total_amb > available_ambulances:
            shortage = total_amb - available_ambulances
            self.engine.add_agent_event(
                self.NAME, "Resource shortage detected",
                request=f"Requested {total_amb} ambulances",
                response=f"Only {available_ambulances} available — SHORTAGE of {shortage}",
                reason="Medical demand exceeds current ambulance fleet"
            )
        if total_teams > available_teams:
            shortage = total_teams - available_teams
            self.engine.add_agent_event(
                self.NAME, "Medical team shortage",
                request=f"Requested {total_teams} teams",
                response=f"Only {available_teams} available — SHORTAGE of {shortage}",
                reason="High patient load across multiple zones"
            )
