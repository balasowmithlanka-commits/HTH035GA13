"""
Rescue Agent — coordinates rescue vehicles and helicopter deployment.
"""
from typing import List, Dict
from models import AffectedZone, ResourcePool, AgentStatus, Priority


class RescueAgent:
    NAME = "Rescue"

    def __init__(self, engine):
        self.engine = engine

    def assess_rescue_needs(self, zones: List[AffectedZone]) -> Dict[str, Dict]:
        """Assess rescue vehicle and helicopter need per zone."""
        self.engine.set_agent_status(self.NAME, AgentStatus.ANALYZING, "Evaluating rescue requirements")

        requests = {}
        for zone in zones:
            # Rescue vehicles: 1 per 800 at risk, min 1
            rescue_vehicles = max(1, zone.rescue_vehicle_requirement)
            # Helicopter: recommend if CRITICAL priority or blocked roads ≥ 3
            heli = 1 if (zone.priority == Priority.CRITICAL or zone.blocked_roads >= 3) else 0
            # Police: 1 unit per 500 at risk, min 2
            import math
            police = max(2, math.ceil(zone.population_at_risk / 500))

            requests[zone.zone_id] = {
                "rescue_vehicles": rescue_vehicles,
                "helicopters": heli,
                "police_units": police,
                "reason": (
                    f"{zone.zone_name}: {zone.population_at_risk} at risk. "
                    f"{'Helicopter needed — ' + str(zone.blocked_roads) + ' roads blocked. ' if heli else ''}"
                    f"Priority: {zone.priority.value}."
                )
            }

        total_resc = sum(r["rescue_vehicles"] for r in requests.values())
        total_heli = sum(r["helicopters"] for r in requests.values())

        self.engine.add_agent_event(
            self.NAME, "Rescue needs assessed",
            request=f"Rescue vehicles: {total_resc} | Helicopters: {total_heli}",
            reason=f"Based on population at risk and road accessibility across {len(zones)} zones"
        )
        self.engine.set_agent_status(self.NAME, AgentStatus.REQUESTING,
                                     f"Requesting {total_resc} rescue vehicles, {total_heli} helicopters")
        return requests

    def prioritise_operations(self, zones: List[AffectedZone]) -> List[str]:
        """Return zones in rescue operation priority order."""
        priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
        sorted_zones = sorted(zones, key=lambda z: (priority_order.get(z.priority, 9), -z.blocked_roads))
        order = [z.zone_name for z in sorted_zones]

        self.engine.add_agent_event(
            self.NAME, "Rescue operation priority set",
            decision=f"Order: {' → '.join(order)}",
            reason="Sorted by priority level then road accessibility"
        )
        self.engine.set_agent_status(self.NAME, AgentStatus.READY, "Rescue priority established")
        return [z.zone_id for z in sorted_zones]
