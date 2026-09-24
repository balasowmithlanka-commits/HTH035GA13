"""
Routing Agent — inspects road conditions, calculates routes, detects blocked roads.
"""
from typing import List, Dict, Optional
from models import AffectedZone, RoadLink, RoadStatus, EvacuationRoute, AgentStatus


class RoutingAgent:
    NAME = "Routing"

    def __init__(self, engine):
        self.engine = engine

    def assess_roads(self, roads: List[RoadLink]) -> Dict:
        """Categorise roads and detect blockages by zone."""
        self.engine.set_agent_status(self.NAME, AgentStatus.CALCULATING, "Assessing road network")

        blocked = [r for r in roads if r.road_status == RoadStatus.BLOCKED]
        flooded = [r for r in roads if r.road_status == RoadStatus.FLOODED]
        open_ = [r for r in roads if r.road_status == RoadStatus.OPEN]

        by_zone: Dict[str, List] = {}
        for r in blocked + flooded:
            for z in [r.from_zone, r.to_zone]:
                by_zone.setdefault(z, []).append(r.road_id)

        report = {
            "total": len(roads),
            "open": len(open_),
            "blocked": len(blocked),
            "flooded": len(flooded),
            "blocked_by_zone": {k: list(set(v)) for k, v in by_zone.items()},
        }

        self.engine.add_agent_event(
            self.NAME, "Road network assessment",
            response=f"Open: {len(open_)} | Blocked: {len(blocked)} | Flooded: {len(flooded)}",
            reason="Based on road dataset water_depth_m and road_status fields"
        )
        return report

    def find_blocked_zones(self, roads: List[RoadLink], zones: List[AffectedZone]) -> List[str]:
        """Find zones that are inaccessible (all entry roads blocked)."""
        inaccessible = []
        for zone in zones:
            entry_roads = [r for r in roads if r.to_zone == zone.zone_id]
            if entry_roads and all(r.road_status != RoadStatus.OPEN for r in entry_roads):
                inaccessible.append(zone.zone_id)
                self.engine.add_agent_event(
                    self.NAME, f"Zone {zone.zone_name} may be inaccessible by road",
                    request=f"Check alternate access for {zone.zone_name}",
                    reason=f"All {len(entry_roads)} entry roads blocked/flooded",
                    zone_id=zone.zone_id
                )
        return inaccessible

    def calculate_routes(self, zones: List[AffectedZone], roads: List[RoadLink]) -> List[EvacuationRoute]:
        """Delegate route calculation to engine and annotate."""
        self.engine.set_agent_status(self.NAME, AgentStatus.CALCULATING, "Computing evacuation routes")
        routes = self.engine.calculate_evacuation_routes()

        blocked_routes = [r for r in routes if r.status != "Open"]
        open_routes = [r for r in routes if r.status == "Open"]

        self.engine.add_agent_event(
            self.NAME, "Evacuation routes calculated",
            response=f"{len(open_routes)} open routes | {len(blocked_routes)} blocked",
            decision=f"Primary routes: {', '.join(r.description for r in open_routes[:3])}",
            reason="Routes selected based on road_status and water_depth_m from dataset"
        )
        self.engine.set_agent_status(
            self.NAME, AgentStatus.READY,
            f"{len(open_routes)} evacuation routes available"
        )
        return routes

    def recommend_helicopter_zones(self, zones: List[AffectedZone], inaccessible: List[str]) -> List[str]:
        """Identify zones needing helicopter support."""
        heli_zones = []
        for zone in zones:
            if zone.zone_id in inaccessible or zone.blocked_roads >= 3:
                heli_zones.append(zone.zone_id)
                self.engine.add_agent_event(
                    self.NAME, f"Helicopter recommended for {zone.zone_name}",
                    request="Helicopter deployment",
                    reason=f"{zone.blocked_roads} roads blocked — ground access limited",
                    zone_id=zone.zone_id
                )
        return heli_zones
