"""
Logistics Agent — manages resource inventory, detects conflicts, allocates supplies.
"""
from typing import List, Dict
from models import AffectedZone, ResourcePool, AgentStatus


class LogisticsAgent:
    NAME = "Logistics"

    def __init__(self, engine):
        self.engine = engine

    def check_inventory(self, resources: ResourcePool) -> Dict:
        """Audit resource pool and flag shortages."""
        self.engine.set_agent_status(self.NAME, AgentStatus.ANALYZING, "Auditing resource inventory")

        report = {
            "ambulances": {"available": resources.ambulances_available, "total": resources.ambulances_total},
            "rescue_vehicles": {"available": resources.rescue_vehicles_available, "total": resources.rescue_vehicles_total},
            "helicopters": {"available": resources.helicopters_available, "total": resources.helicopters_total},
            "medical_teams": {"available": resources.medical_teams_available, "total": resources.medical_teams_total},
            "food": {"available": resources.food_available, "total": resources.food_total},
            "water": {"available": resources.water_available, "total": resources.water_total},
            "medical_supplies": {"available": resources.medical_supplies_available, "total": resources.medical_supplies_total},
            "shelter": {"available": resources.shelter_available, "total": resources.shelter_total},
            "shortages": [],
        }

        # Flag critical shortages
        thresholds = {"ambulances": 5, "rescue_vehicles": 4, "medical_teams": 5}
        for key, threshold in thresholds.items():
            if report[key]["available"] < threshold:
                report["shortages"].append(f"{key.replace('_',' ').title()}: only {report[key]['available']} available")

        self.engine.add_agent_event(
            self.NAME, "Inventory check complete",
            response=f"Ambulances: {resources.ambulances_available}/{resources.ambulances_total} | "
                     f"Rescue: {resources.rescue_vehicles_available}/{resources.rescue_vehicles_total} | "
                     f"Helicopters: {resources.helicopters_available}/{resources.helicopters_total} | "
                     f"Shortages: {len(report['shortages'])}",
        )
        return report

    def compute_supply_allocations(self, zones: List[AffectedZone], resources: ResourcePool) -> Dict[str, Dict]:
        """
        Allocate food, water, shelter, evac vehicles proportional to zone priority.
        Returns {zone_id: {food, water, shelter_slots, evacuation_vehicles}}
        """
        self.engine.set_agent_status(self.NAME, AgentStatus.REALLOCATING, "Computing supply allocations")

        # Priority weights
        weight_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        weights = {z.zone_id: weight_map.get(z.priority.value, 1) for z in zones}
        total_weight = sum(weights.values()) or 1

        allocs = {}
        for zone in zones:
            w = weights[zone.zone_id]
            food = min(int(resources.food_available * w / total_weight), zone.food_requirement)
            water = min(int(resources.water_available * w / total_weight), zone.water_requirement)
            shelter = min(int(resources.shelter_available * w / total_weight), zone.shelter_demand)
            evac_v = max(1, int(resources.evacuation_vehicles_available * w / total_weight))

            allocs[zone.zone_id] = {
                "food_packets": food,
                "water_litres": water,
                "shelter_slots": shelter,
                "evacuation_vehicles": evac_v,
                "reason": f"Priority {zone.priority.value} (weight {w}/{total_weight}) → proportional allocation"
            }

        self.engine.add_agent_event(
            self.NAME, "Supply allocation computed",
            decision=f"Proportional supply distribution across {len(zones)} zones",
            reason="Weighted by zone priority: CRITICAL=4x, HIGH=3x, MEDIUM=2x, LOW=1x"
        )

        self.engine.set_agent_status(self.NAME, AgentStatus.READY, "Supply plan ready")
        return allocs

    def detect_conflicts(self, medical_requests: Dict, resources: ResourcePool) -> List[str]:
        """Detect resource conflicts between agent requests and available pool."""
        conflicts = []
        total_amb = sum(r.get("ambulances", 0) for r in medical_requests.values())
        total_teams = sum(r.get("medical_teams", 0) for r in medical_requests.values())

        if total_amb > resources.ambulances_available:
            conflicts.append(
                f"Ambulance conflict: {total_amb} requested by Medical Agent, "
                f"only {resources.ambulances_available} available"
            )
        if total_teams > resources.medical_teams_available:
            conflicts.append(
                f"Medical team conflict: {total_teams} requested, "
                f"only {resources.medical_teams_available} available"
            )

        if conflicts:
            self.engine.add_agent_event(
                self.NAME, "Resource conflict detected",
                response=f"{len(conflicts)} conflicts found",
                reason="; ".join(conflicts)
            )
            self.engine.set_agent_status(self.NAME, AgentStatus.REALLOCATING, f"{len(conflicts)} conflicts to resolve")
        return conflicts
