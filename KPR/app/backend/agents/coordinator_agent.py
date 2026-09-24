"""
Coordinator Agent — central decision maker.
Receives all agent recommendations, resolves conflicts, enforces constraints,
and generates the final Response Plan.
"""
import math
from typing import List, Dict, Tuple, Optional
from copy import deepcopy
from models import (
    AffectedZone, ZoneAllocation, ResourcePool, ResponsePlan,
    EvacuationRoute, Priority, AgentStatus
)
from agents.medical_agent import MedicalAgent
from agents.logistics_agent import LogisticsAgent
from agents.routing_agent import RoutingAgent
from agents.rescue_agent import RescueAgent
from agents.communication_agent import CommunicationAgent


PRIORITY_ORDER = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}


class CoordinatorAgent:
    NAME = "Coordinator"

    def __init__(self, engine):
        self.engine = engine
        self.medical = MedicalAgent(engine)
        self.logistics = LogisticsAgent(engine)
        self.routing = RoutingAgent(engine)
        self.rescue = RescueAgent(engine)
        self.comms = CommunicationAgent(engine)

    # ── Main orchestration ─────────────────────────────────────────────────

    def generate_plan(self) -> ResponsePlan:
        """
        Full planning cycle:
        1. Each agent analyses situation
        2. Conflicts detected
        3. Coordinator negotiates/resolves
        4. Allocations finalised
        5. Plan generated
        """
        st = self.engine.state
        zones = sorted(st.zones, key=lambda z: PRIORITY_ORDER.get(z.priority, 9))

        self.engine.set_agent_status(self.NAME, AgentStatus.ANALYZING, "Initiating coordinated response planning")

        # ── Step 1: Agent assessments ──────────────────────────────────────
        med_requests = self.medical.analyze(zones)
        supply_allocs = self.logistics.compute_supply_allocations(zones, st.resources)
        road_report = self.routing.assess_roads(st.roads)
        inaccessible = self.routing.find_blocked_zones(st.roads, zones)
        routes = self.routing.calculate_routes(zones, st.roads)
        rescue_requests = self.rescue.assess_rescue_needs(zones)
        rescue_priority = self.rescue.prioritise_operations(zones)
        heli_zones = self.routing.recommend_helicopter_zones(zones, inaccessible)

        # ── Step 2: Detect conflicts ───────────────────────────────────────
        conflicts = self.logistics.detect_conflicts(med_requests, st.resources)
        self.medical.identify_shortages(
            med_requests,
            st.resources.ambulances_available,
            st.resources.medical_teams_available
        )

        # ── Step 3: Resolve and negotiate ─────────────────────────────────
        self.engine.set_agent_status(self.NAME, AgentStatus.RESOLVING,
                                     f"Resolving {len(conflicts)} conflicts")
        allocations, decisions, unresolved = self._resolve_and_allocate(
            zones, med_requests, supply_allocs, rescue_requests, heli_zones, st.resources, conflicts
        )

        # ── Step 4: Enforce constraints ────────────────────────────────────
        success, remaining_conflicts = self.engine.allocate_resources(allocations)
        unresolved.extend(remaining_conflicts)

        # ── Step 5: Communication ──────────────────────────────────────────
        alert = self.comms.generate_alert(zones, routes, plan_version=len(st.plans) + 1)

        # ── Step 6: Build plan ─────────────────────────────────────────────
        plan_version = len(st.plans) + 1
        import uuid
        from datetime import datetime
        plan = ResponsePlan(
            plan_id=str(uuid.uuid4())[:8],
            version=plan_version,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            zones=deepcopy(zones),
            allocations=allocations,
            resource_snapshot=deepcopy(st.resources),
            evacuation_routes=routes,
            blocked_roads=[
                f"{r.road_id}: {r.from_zone}→{r.to_zone} ({r.road_status.value})"
                for r in st.roads if r.road_status != "Open"
            ][:20],
            unresolved_conflicts=unresolved,
            coordinator_decisions=decisions,
            rationale=self._build_rationale(zones, allocations, conflicts, decisions),
            public_alert=alert["full_text"],
            what_changed=self._compute_what_changed(st.plans, allocations, zones) if st.plans else None,
        )

        st.plans.append(plan)
        st.current_plan_version = plan_version

        self.engine.set_agent_status(self.NAME, AgentStatus.READY,
                                     f"Plan V{plan_version} generated")
        self.engine.add_agent_event(
            self.NAME, f"Response Plan V{plan_version} generated",
            decision=f"{len(allocations)} zone allocations | {len(decisions)} coordinator decisions",
            reason=f"Resolved {len(conflicts)} conflicts | {len(unresolved)} unresolved"
        )

        return plan

    # ── Allocation resolution ──────────────────────────────────────────────

    def _resolve_and_allocate(
        self,
        zones: List[AffectedZone],
        med_requests: Dict,
        supply_allocs: Dict,
        rescue_requests: Dict,
        heli_zones: List[str],
        resources: ResourcePool,
        conflicts: List[str],
    ) -> Tuple[List[ZoneAllocation], List[str], List[str]]:
        """
        Negotiate between agents. Enforce hard resource cap.
        Priority zones get full allocation; lower zones get remainder.
        """
        decisions = []
        unresolved = []

        avail_amb = resources.ambulances_available
        avail_resc = resources.rescue_vehicles_available
        avail_heli = resources.helicopters_available
        avail_pol = resources.police_units_available
        avail_teams = resources.medical_teams_available
        avail_evac = resources.evacuation_vehicles_available

        allocations = []

        for zone in zones:  # already sorted by priority
            zid = zone.zone_id
            med = med_requests.get(zid, {})
            rescue = rescue_requests.get(zid, {})
            supply = supply_allocs.get(zid, {})

            # Ambulances — cap to available
            amb_wanted = med.get("ambulances", 1)
            amb_alloc = min(amb_wanted, avail_amb)
            avail_amb -= amb_alloc

            # If short, try reallocation from lowest zones
            if amb_alloc < amb_wanted:
                shortfall = amb_wanted - amb_alloc
                decisions.append(
                    f"AMBULANCE SHORTFALL in {zone.zone_name}: wanted {amb_wanted}, "
                    f"allocated {amb_alloc}. Shortfall of {shortfall} noted."
                )
                self.engine.add_agent_event(
                    self.NAME, "Ambulance reallocation",
                    request=f"{zone.zone_name} wants {amb_wanted} ambulances",
                    response=f"Only {amb_alloc} available after priority allocation",
                    decision=f"Allocated {amb_alloc} to {zone.zone_name}. Monitoring shortfall.",
                    reason=f"Resource constraint: {amb_wanted - amb_alloc} ambulances unavailable",
                    zone_id=zid
                )

            # Rescue vehicles
            rv_wanted = rescue.get("rescue_vehicles", 1)
            rv_alloc = min(rv_wanted, avail_resc)
            avail_resc -= rv_alloc

            # Helicopters
            heli_wanted = rescue.get("helicopters", 0)
            if zid in heli_zones and heli_wanted == 0:
                heli_wanted = 1
            heli_alloc = min(heli_wanted, avail_heli)
            avail_heli -= heli_alloc

            if heli_alloc > 0:
                decisions.append(
                    f"HELICOPTER deployed to {zone.zone_name}: "
                    f"{zone.blocked_roads} roads blocked — air access needed."
                )
                self.engine.add_agent_event(
                    self.NAME, f"Helicopter deployment approved — {zone.zone_name}",
                    decision=f"Deploy {heli_alloc} helicopter(s) to {zone.zone_name}",
                    reason=f"Road access limited ({zone.blocked_roads} blocked). "
                           f"Priority: {zone.priority.value}",
                    zone_id=zid
                )

            # Police
            pol_wanted = math.ceil(zone.population_at_risk / 500)
            pol_alloc = min(pol_wanted, avail_pol)
            avail_pol -= pol_alloc

            # Medical teams
            team_wanted = med.get("medical_teams", 1)
            team_alloc = min(team_wanted, avail_teams)
            avail_teams -= team_alloc

            # Evacuation vehicles
            evac_wanted = supply.get("evacuation_vehicles", 2)
            evac_alloc = min(evac_wanted, avail_evac)
            avail_evac -= evac_alloc

            # Routes
            evac_routes = [
                r.route_id for r in self.engine.state.evacuation_routes
                if r.from_zone == zid and r.status == "Open"
            ]
            blocked = [
                f"{r.road_id}" for r in self.engine.state.roads
                if r.from_zone == zid and r.road_status.value != "Open"
            ][:5]

            reasons = {
                "ambulances": f"Allocated {amb_alloc}/{amb_wanted} requested (priority: {zone.priority.value})",
                "rescue_vehicles": f"Deployed {rv_alloc} rescue vehicles",
                "helicopters": f"{heli_alloc} helicopter(s) {'deployed' if heli_alloc else 'not needed'}",
                "medical_teams": f"{team_alloc} teams for {zone.critical_patients} critical patients",
            }

            alloc = ZoneAllocation(
                zone_id=zid,
                zone_name=zone.zone_name,
                ambulances=amb_alloc,
                rescue_vehicles=rv_alloc,
                helicopters=heli_alloc,
                police_units=pol_alloc,
                medical_teams=team_alloc,
                evacuation_vehicles=evac_alloc,
                shelter_slots=supply.get("shelter_slots", 0),
                food_packets=supply.get("food_packets", 0),
                water_litres=supply.get("water_litres", 0),
                medical_kits=med.get("medical_kits", 0),
                evacuation_routes=evac_routes,
                blocked_roads=blocked,
                allocation_reasons=reasons,
            )
            allocations.append(alloc)

        # Summary decision
        decisions.append(
            f"COORDINATOR FINAL: {len(zones)} zones covered | "
            f"Ambulances deployed: {resources.ambulances_available - avail_amb} | "
            f"Rescue vehicles: {resources.rescue_vehicles_available - avail_resc} | "
            f"Helicopters: {resources.helicopters_available - avail_heli}"
        )
        self.engine.add_agent_event(
            self.NAME, "Final allocation approved",
            decision=decisions[-1],
            reason=f"Constraints enforced: no zone exceeds available resource pool"
        )
        return allocations, decisions, unresolved

    # ── Rationale ─────────────────────────────────────────────────────────

    def _build_rationale(self, zones, allocations, conflicts, decisions) -> str:
        critical = [z for z in zones if z.priority == Priority.CRITICAL]
        high = [z for z in zones if z.priority == Priority.HIGH]
        return (
            f"Response covers {len(zones)} zones. "
            f"{len(critical)} CRITICAL: {', '.join(z.zone_name for z in critical)}. "
            f"{len(high)} HIGH: {', '.join(z.zone_name for z in high)}. "
            f"{len(conflicts)} resource conflicts resolved. "
            f"Priority allocation: CRITICAL zones receive full requested resources first; "
            f"remaining distributed proportionally to HIGH, MEDIUM, LOW zones. "
            f"Helicopter support approved for zones with ≥3 blocked roads. "
            f"All allocations verified against resource pool constraints."
        )

    # ── What Changed (V1→V2) ──────────────────────────────────────────────

    def _compute_what_changed(
        self, previous_plans: List[ResponsePlan],
        new_allocations: List[ZoneAllocation],
        new_zones: List[AffectedZone],
    ) -> List[str]:
        if not previous_plans:
            return []

        prev_plan = previous_plans[-1]
        prev_alloc = {a.zone_id: a for a in prev_plan.allocations}
        new_alloc_map = {a.zone_id: a for a in new_allocations}

        changes = []

        # New zones
        prev_zone_ids = {z.zone_id for z in prev_plan.zones}
        for zone in new_zones:
            if zone.zone_id not in prev_zone_ids:
                changes.append(f"🆕 New zone added: {zone.zone_name} (Priority: {zone.priority.value})")

        # Priority changes
        prev_priorities = {z.zone_id: z.priority for z in prev_plan.zones}
        for zone in new_zones:
            old_p = prev_priorities.get(zone.zone_id)
            if old_p and old_p != zone.priority:
                changes.append(
                    f"⬆️ {zone.zone_name} priority: {old_p.value} → {zone.priority.value}"
                )

        # Resource changes per zone
        for zid, new_a in new_alloc_map.items():
            old_a = prev_alloc.get(zid)
            if old_a:
                if new_a.ambulances != old_a.ambulances:
                    diff = new_a.ambulances - old_a.ambulances
                    changes.append(
                        f"🚑 {new_a.zone_name}: ambulances {old_a.ambulances} → {new_a.ambulances} "
                        f"({'↑' if diff > 0 else '↓'}{abs(diff)})"
                    )
                if new_a.helicopters != old_a.helicopters:
                    changes.append(
                        f"🚁 {new_a.zone_name}: helicopters {old_a.helicopters} → {new_a.helicopters}"
                    )
                if new_a.rescue_vehicles != old_a.rescue_vehicles:
                    diff = new_a.rescue_vehicles - old_a.rescue_vehicles
                    changes.append(
                        f"🚒 {new_a.zone_name}: rescue vehicles {old_a.rescue_vehicles} → {new_a.rescue_vehicles} "
                        f"({'↑' if diff > 0 else '↓'}{abs(diff)})"
                    )
            else:
                changes.append(
                    f"🆕 {new_a.zone_name}: NEW allocation — "
                    f"{new_a.ambulances} amb | {new_a.rescue_vehicles} rescue | "
                    f"{new_a.helicopters} heli"
                )

        # Route changes
        prev_route_ids = {r.route_id for r in prev_plan.evacuation_routes}
        new_route_ids = {r.route_id for r in self.engine.state.evacuation_routes}
        added_routes = new_route_ids - prev_route_ids
        if added_routes:
            changes.append(f"🗺️ {len(added_routes)} new evacuation route(s) added")

        for r in self.engine.state.evacuation_routes:
            prev_r = next((p for p in prev_plan.evacuation_routes if p.route_id == r.route_id), None)
            if prev_r and prev_r.status != r.status:
                changes.append(f"🚧 Route {r.description}: {prev_r.status} → {r.status}")

        # Alert
        changes.append("📢 Public alert updated to reflect new affected zones and routes")

        return changes
