"""
Communication Agent — generates public emergency alerts.
NOTE: All alerts are SIMULATION OUTPUT only. Not official government communications.
"""
from typing import List, Optional
from models import AffectedZone, EvacuationRoute, AgentStatus, Priority


class CommunicationAgent:
    NAME = "Communication"

    def __init__(self, engine):
        self.engine = engine

    def generate_alert(self, zones: List[AffectedZone], routes: List[EvacuationRoute],
                       plan_version: int = 1) -> dict:
        """
        Generate a public emergency alert.
        SIMULATION ONLY — not an official government communication.
        """
        self.engine.set_agent_status(self.NAME, AgentStatus.UPDATING, "Preparing public alert")

        critical_zones = [z for z in zones if z.priority == Priority.CRITICAL]
        high_zones = [z for z in zones if z.priority == Priority.HIGH]
        open_routes = [r for r in routes if r.status == "Open"]
        blocked_routes = [r for r in routes if r.status != "Open"]

        # Overall severity
        if critical_zones:
            overall = "CRITICAL"
        elif high_zones:
            overall = "HIGH"
        else:
            overall = "MODERATE"

        # Affected area list
        affected_areas = ", ".join(z.zone_name for z in zones)
        critical_area_names = ", ".join(z.zone_name for z in critical_zones) if critical_zones else "None"

        # Shelter info
        shelter_zones = critical_zones[:2] if critical_zones else high_zones[:2]
        shelter_text = "; ".join(
            f"Nearest shelter from {z.zone_name}: contact local corporation" for z in shelter_zones
        )

        # Route info
        evac_text = " | ".join(r.description for r in open_routes[:3]) if open_routes else "Under assessment"
        closed_text = " | ".join(r.description for r in blocked_routes[:3]) if blocked_routes else "None"

        total_at_risk = sum(z.population_at_risk for z in zones)
        total_critical = sum(z.critical_patients for z in zones)

        alert_text = (
            f"[SIMULATION ALERT — Plan V{plan_version}] "
            f"⚠️ Chennai Flood Emergency — {overall} ALERT\n\n"
            f"Affected Areas: {affected_areas}\n"
            f"Critical Zones: {critical_area_names}\n"
            f"Estimated population at risk: {total_at_risk:,}\n"
            f"Critical patients: {total_critical}\n\n"
            f"Evacuation Routes Open: {evac_text}\n"
            f"Road Closures: {closed_text}\n\n"
            f"Shelters: {shelter_text}\n\n"
            f"Emergency Contacts: Chennai NDRF — 1078 | Ambulance — 108 | Fire — 101\n"
            f"[This is a disaster response simulation — not an official government alert]"
        )

        self.engine.state.public_alert = alert_text
        self.engine.state.alert_severity = overall

        self.engine.add_agent_event(
            self.NAME, f"Public alert generated (Plan V{plan_version})",
            decision=f"Alert severity: {overall} | Zones covered: {len(zones)}",
            reason=f"{len(critical_zones)} CRITICAL zones, {len(high_zones)} HIGH zones detected"
        )
        self.engine.set_agent_status(self.NAME, AgentStatus.READY,
                                     f"Alert issued — {overall} severity")

        return {
            "severity": overall,
            "affected_areas": affected_areas,
            "critical_zones": critical_area_names,
            "evacuation_routes": evac_text,
            "road_closures": closed_text,
            "shelter_info": shelter_text,
            "total_at_risk": total_at_risk,
            "total_critical": total_critical,
            "full_text": alert_text,
            "plan_version": plan_version,
        }
