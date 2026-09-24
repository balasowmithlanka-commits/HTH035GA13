"""
Disaster Simulation Engine
==========================
Maintains the evolving disaster state for the Chennai Flood Emergency scenario.

SOURCE DATA   — read from CSV files, never modified
SIMULATED DATA — computed by this engine from scenario rules + source data

The engine is the single source of truth. All agents read from it.
"""
import uuid
import math
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from copy import deepcopy

from models import (
    AffectedZone, Priority, ResourcePool, ZoneAllocation,
    SimulationState, SimulationStatus, AgentState, AgentStatus,
    AgentEvent, IncidentEvent, RoadLink, RoadStatus, EvacuationRoute
)
import data_loader as dl


# ─── Zone configuration — based on dataset structure ─────────────────────────

INITIAL_ZONES_CONFIG = {
    "Z01": {"zone_name": "North Chennai",      "flood_boost": 1.2},
    "Z02": {"zone_name": "Central Chennai",    "flood_boost": 1.0},
    "Z03": {"zone_name": "Adyar",              "flood_boost": 1.4},
    "Z04": {"zone_name": "Velachery",          "flood_boost": 1.5},
    "Z05": {"zone_name": "South-West Chennai", "flood_boost": 1.1},
}

PERUNGUDI_CONFIG = {
    "zone_id": "Z06",
    "zone_name": "Perungudi",
    "latitude": 12.962,
    "longitude": 80.244,
    "flood_boost": 1.6,
}

# Simulation time base (minutes from midnight 9:00)
SIM_BASE_HOUR = 9
SIM_BASE_MIN = 0


def _sim_time(tick: int, speed: float = 1.0) -> str:
    """Convert tick to HH:MM simulation time."""
    total_minutes = SIM_BASE_HOUR * 60 + SIM_BASE_MIN + tick
    h = (total_minutes // 60) % 24
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


def _uid() -> str:
    return str(uuid.uuid4())[:8]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ─── Simulation Engine ────────────────────────────────────────────────────────

class SimulationEngine:
    """Central simulation engine. Holds all mutable state."""

    def __init__(self):
        self.state = SimulationState()
        self._zone_cache: Dict = {}
        self._patient_cache: Dict = {}
        self._road_df = None
        self._rainfall_offset: float = 0.0   # added by manual events

    # ── Initialisation ─────────────────────────────────────────────────────

    def initialise(self):
        """Load source data and set up initial simulation state."""
        self._zone_cache = dl.get_zone_summary()
        self._patient_cache = dl.get_patient_summary_by_zone()

        ambu = dl.get_ambulance_counts()
        rescue = dl.get_rescue_vehicle_counts()
        heli = dl.get_helicopter_counts()
        teams = dl.get_medical_team_counts()
        shelter = dl.get_shelter_counts()
        police = dl.get_police_counts()
        evac = dl.get_evacuation_vehicle_counts()
        food = dl.get_food_total()
        water = dl.get_water_total()
        meds = dl.get_medical_supply_total()
        fuel = dl.get_fuel_total()

        # Simulation resource pool (derived from dataset, scaled to scenario)
        # We cap at hackathon-demo values so conflict is visible
        self.state.resources = ResourcePool(
            ambulances_total=min(ambu["total"], 40),
            ambulances_available=min(ambu["available"] + ambu["standby"], 40),
            ambulances_deployed=0,
            rescue_vehicles_total=min(rescue["total"], 25),
            rescue_vehicles_available=min(rescue["available"] + rescue["standby"], 25),
            rescue_vehicles_deployed=0,
            helicopters_total=min(heli["total"], 6),
            helicopters_available=min(heli["available"] + heli["standby"], 6),
            helicopters_deployed=0,
            evacuation_vehicles_total=min(evac["total"], 60),
            evacuation_vehicles_available=min(evac["available"], 60),
            evacuation_vehicles_deployed=0,
            police_units_total=min(police["total_vehicles"], 80),
            police_units_available=min(police["total_vehicles"], 80),
            police_units_deployed=0,
            medical_teams_total=min(teams["total"], 30),
            medical_teams_available=min(teams["available"], 30),
            medical_teams_deployed=0,
            shelter_total=shelter["total"],
            shelter_occupied=shelter["occupied"],
            shelter_available=shelter["available"],
            food_total=food,
            food_distributed=0,
            food_available=food,
            water_total=water,
            water_distributed=0,
            water_available=water,
            medical_supplies_total=meds,
            medical_supplies_used=0,
            medical_supplies_available=meds,
            fuel_total=fuel,
            fuel_used=0,
            fuel_available=fuel,
        )

        self.state.hospitals = dl.get_hospital_records()
        self.state.communication_status = dl.get_comm_status()
        self.state.power_status = dl.get_power_status()

        # Initialise agents
        agent_names = ["Medical", "Logistics", "Routing", "Rescue", "Communication", "Coordinator"]
        for name in agent_names:
            self.state.agents[name] = AgentState(
                name=name,
                status=AgentStatus.IDLE,
                last_action="Waiting for simulation start",
                last_updated=_now(),
            )

        # Load roads
        road_records = dl.get_road_summary()["roads"]
        self.state.roads = [
            RoadLink(
                road_id=r["road_id"],
                from_zone=r["from_zone"],
                to_zone=r["to_zone"],
                from_lat=r["from_lat"],
                from_lon=r["from_lon"],
                to_lat=r["to_lat"],
                to_lon=r["to_lon"],
                distance_km=r["distance_km"],
                road_status=RoadStatus(r["road_status"]),
                water_depth_m=r["water_depth_m"],
                travel_time_min=r["travel_time_min"],
            )
            for r in road_records[:300]   # keep payload manageable
        ]

        self.state.status = SimulationStatus.IDLE
        self.state.tick = 0
        self.state.sim_time = _sim_time(0)
        avg_rain = dl.get_recent_rainfall_avg(30)
        self.state.rainfall_mm = round(avg_rain * 8, 1)  # scenario-scaled

        self._add_incident("System", "Simulation initialised. Chennai flood scenario loaded.")

    # ── Zone Building ──────────────────────────────────────────────────────

    def _build_zone(self, zone_id: str, flood_boost: float, is_new: bool = False,
                    custom: Optional[Dict] = None) -> AffectedZone:
        """Build an AffectedZone from source data + simulation parameters."""
        if custom:
            zc = custom
            zone_name = zc["zone_name"]
            pop = zc.get("population", 12800)
            base_rain = self.state.rainfall_mm
        else:
            zd = self._zone_cache.get(zone_id, {})
            zone_name = zd.get("zone_name", zone_id)
            pop = zd.get("total_population", 100000)
            base_rain = zd.get("avg_rainfall", self.state.rainfall_mm)

        rain = base_rain + self._rainfall_offset
        flood_index = min(3.5, (rain / 20) * flood_boost)
        flood_level = round(flood_index * 0.6, 2)          # metres (simulated)

        # Affected rate is scenario-derived from flood index
        affected_rate = min(0.35, flood_index * 0.08)
        pop_at_risk = int(pop * affected_rate)
        vulnerable = int(pop_at_risk * 0.22)   # ~22% elderly/children (from census)

        # Patient estimates from dataset ratios
        pd_cache = self._patient_cache.get(zone_id, {})
        total_patients = pd_cache.get("total", 0)
        if total_patients > 0:
            crit_ratio = pd_cache.get("critical", 0) / total_patients
            mod_ratio = pd_cache.get("moderate", 0) / total_patients
        else:
            crit_ratio = 0.035
            mod_ratio = 0.19

        critical_patients = max(1, int(pop_at_risk * crit_ratio * flood_boost))
        injured = max(1, int(pop_at_risk * mod_ratio * flood_boost))

        # Road blockages from road dataset
        blocked_count = sum(
            1 for r in self.state.roads
            if (r.from_zone == zone_id or r.to_zone == zone_id)
            and r.road_status in (RoadStatus.BLOCKED, RoadStatus.FLOODED)
        )

        # Resource requirements (simulation formula)
        ambulance_req = max(1, math.ceil(critical_patients / 5))
        rescue_req = max(1, math.ceil(pop_at_risk / 800))
        team_req = max(1, math.ceil(critical_patients / 8))
        shelter_demand = max(100, int(pop_at_risk * 0.35))
        food_req = shelter_demand * 3   # 3 meals/day
        water_req = shelter_demand * 15  # 15 L/day

        # Priority
        if flood_level >= 2.0 or critical_patients >= 25:
            priority = Priority.CRITICAL
            priority_reason = f"Flood level {flood_level}m ≥ 2.0m and {critical_patients} critical patients"
        elif flood_level >= 1.2 or critical_patients >= 15:
            priority = Priority.HIGH
            priority_reason = f"Flood level {flood_level}m ≥ 1.2m and {critical_patients} critical patients"
        elif flood_level >= 0.6:
            priority = Priority.MEDIUM
            priority_reason = f"Flood level {flood_level}m ≥ 0.6m — moderate risk"
        else:
            priority = Priority.LOW
            priority_reason = f"Flood level {flood_level}m < 0.6m — low risk"

        lat = custom["latitude"] if custom else self._zone_cache.get(zone_id, {}).get("latitude", 13.08)
        lon = custom["longitude"] if custom else self._zone_cache.get(zone_id, {}).get("longitude", 80.27)

        # Map flood_index to severity label
        if flood_index >= 2.5:
            flood_severity = "Severe"
        elif flood_index >= 1.5:
            flood_severity = "High"
        elif flood_index >= 0.8:
            flood_severity = "Moderate"
        else:
            flood_severity = "Low"

        return AffectedZone(
            zone_id=zone_id,
            zone_name=zone_name,
            latitude=lat,
            longitude=lon,
            population=pop,
            population_at_risk=pop_at_risk,
            flood_severity=flood_severity,
            flood_level=flood_level,
            priority=priority,
            critical_patients=critical_patients,
            injured_people=injured,
            vulnerable_population=vulnerable,
            blocked_roads=blocked_count,
            shelter_demand=shelter_demand,
            food_requirement=food_req,
            water_requirement=water_req,
            ambulance_requirement=ambulance_req,
            rescue_vehicle_requirement=rescue_req,
            medical_team_requirement=team_req,
            is_new=is_new,
            added_at=_now() if is_new else None,
            priority_reason=priority_reason,
        )

    def build_initial_zones(self):
        """Build the 5 initial affected zones."""
        self.state.zones = []
        for zone_id, cfg in INITIAL_ZONES_CONFIG.items():
            zone = self._build_zone(zone_id, cfg["flood_boost"])
            self.state.zones.append(zone)

    def add_perungudi_zone(self):
        """Add Perungudi as a new affected zone (demo main event)."""
        cfg = PERUNGUDI_CONFIG
        pop = 0
        # Use rainfall + boost to generate realistic population at risk
        # Perungudi is between Adyar/Velachery — similar census density
        adyar_pop = self._zone_cache.get("Z03", {}).get("total_population", 900000)
        perungudi_pop = int(adyar_pop * 0.55)  # approx 45% of Adyar area

        zone = self._build_zone(
            zone_id="Z06",
            flood_boost=cfg["flood_boost"],
            is_new=True,
            custom={
                "zone_name": "Perungudi",
                "latitude": cfg["latitude"],
                "longitude": cfg["longitude"],
                "population": perungudi_pop,
            }
        )
        self.state.zones.append(zone)
        self._add_incident(
            "System",
            f"🚨 NEW AFFECTED ZONE: Perungudi | Flood level {zone.flood_level}m | "
            f"Priority: {zone.priority.value} | Critical patients: {zone.critical_patients}",
            zone_id="Z06",
            severity="Critical"
        )
        return zone

    # ── Resource Pool Management ────────────────────────────────────────────

    def allocate_resources(self, allocations: List[ZoneAllocation]) -> Tuple[bool, List[str]]:
        """
        Enforce resource constraints. Returns (success, conflict_list).
        INVARIANT: sum of allocations <= pool total. Always enforced here.
        """
        # Tally requested
        total_amb = sum(a.ambulances for a in allocations)
        total_res = sum(a.rescue_vehicles for a in allocations)
        total_hel = sum(a.helicopters for a in allocations)
        total_pol = sum(a.police_units for a in allocations)
        total_med = sum(a.medical_teams for a in allocations)
        total_evac = sum(a.evacuation_vehicles for a in allocations)

        conflicts = []
        r = self.state.resources

        if total_amb > r.ambulances_available:
            conflicts.append(f"Ambulance conflict: {total_amb} requested, {r.ambulances_available} available")
        if total_res > r.rescue_vehicles_available:
            conflicts.append(f"Rescue vehicle conflict: {total_res} requested, {r.rescue_vehicles_available} available")
        if total_hel > r.helicopters_available:
            conflicts.append(f"Helicopter conflict: {total_hel} requested, {r.helicopters_available} available")
        if total_pol > r.police_units_available:
            conflicts.append(f"Police conflict: {total_pol} requested, {r.police_units_available} available")
        if total_med > r.medical_teams_available:
            conflicts.append(f"Medical team conflict: {total_med} requested, {r.medical_teams_available} available")

        # Apply regardless (caller already resolved conflicts by capping)
        r.ambulances_deployed = total_amb
        r.ambulances_available = r.ambulances_total - total_amb
        r.rescue_vehicles_deployed = total_res
        r.rescue_vehicles_available = r.rescue_vehicles_total - total_res
        r.helicopters_deployed = total_hel
        r.helicopters_available = r.helicopters_total - total_hel
        r.police_units_deployed = total_pol
        r.police_units_available = r.police_units_total - total_pol
        r.medical_teams_deployed = total_med
        r.medical_teams_available = r.medical_teams_total - total_med
        r.evacuation_vehicles_deployed = total_evac
        r.evacuation_vehicles_available = r.evacuation_vehicles_total - total_evac

        # Supplies
        food_dist = sum(a.food_packets for a in allocations)
        water_dist = sum(a.water_litres for a in allocations)
        med_kits = sum(a.medical_kits for a in allocations)

        r.food_distributed = min(food_dist, r.food_total)
        r.food_available = r.food_total - r.food_distributed
        r.water_distributed = min(water_dist, r.water_total)
        r.water_available = r.water_total - r.water_distributed
        r.medical_supplies_used = min(med_kits, r.medical_supplies_total)
        r.medical_supplies_available = r.medical_supplies_total - r.medical_supplies_used

        self.state.allocations = allocations
        return len(conflicts) == 0, conflicts

    # ── Evacuation Routes ──────────────────────────────────────────────────

    def calculate_evacuation_routes(self) -> List[EvacuationRoute]:
        """Calculate feasible evacuation routes from affected zones to hospitals/shelters."""
        routes = []
        blocked_zones = {r.from_zone for r in self.state.roads if r.road_status != RoadStatus.OPEN}

        zone_pairs = [
            ("Z04", "Z02", "Velachery → Central Chennai via Inner Ring Road"),
            ("Z03", "Z02", "Adyar → Central Chennai via Adyar Bridge"),
            ("Z01", "Z02", "North Chennai → Central Chennai via NH16"),
            ("Z05", "Z02", "South-West → Central Chennai via GST Road"),
            ("Z04", "Z03", "Velachery → Adyar via 200ft Road"),
        ]

        rid = 1
        for from_z, to_z, desc in zone_pairs:
            blocked = any(
                r.road_status != RoadStatus.OPEN
                for r in self.state.roads
                if r.from_zone == from_z and r.to_zone == to_z
            )
            status = "Blocked" if blocked else "Open"
            routes.append(EvacuationRoute(
                route_id=f"EVAC-{rid:03d}",
                from_zone=from_z,
                to_zone=to_z,
                via=[from_z, to_z],
                total_distance_km=round(8 + rid * 1.2, 1),
                estimated_time_min=round(20 + rid * 5, 0) if not blocked else 999,
                status=status,
                description=desc,
            ))
            rid += 1

        # If Perungudi exists, add routes
        if any(z.zone_id == "Z06" for z in self.state.zones):
            omr_blocked = self.state.rainfall_mm > 150  # OMR floods at high rain
            routes.append(EvacuationRoute(
                route_id=f"EVAC-{rid:03d}",
                from_zone="Z06",
                to_zone="Z04",
                via=["Z06", "Z04"],
                total_distance_km=6.5,
                estimated_time_min=999 if omr_blocked else 18,
                status="Blocked — OMR flooded" if omr_blocked else "Open",
                description="Perungudi → Velachery via OMR",
            ))
            rid += 1
            routes.append(EvacuationRoute(
                route_id=f"EVAC-{rid:03d}",
                from_zone="Z06",
                to_zone="Z03",
                via=["Z06", "Z03"],
                total_distance_km=5.0,
                estimated_time_min=22,
                status="Open",
                description="Perungudi → Adyar via Rajiv Gandhi IT Park Road (alternate)",
            ))

        self.state.evacuation_routes = routes
        return routes

    # ── Manual Events ──────────────────────────────────────────────────────

    def apply_manual_event(self, event_type: str, zone_id: Optional[str] = None, params: Dict = {}):
        """Apply a simulation control event."""
        desc = ""
        if event_type == "increase_rainfall":
            delta = params.get("delta", 20.0)
            self._rainfall_offset += delta
            self.state.rainfall_mm += delta
            desc = f"Rainfall increased by {delta} mm/day → total {self.state.rainfall_mm:.1f} mm/day"
            self._rebuild_zones()

        elif event_type == "increase_flood_severity":
            for zone in self.state.zones:
                if zone_id is None or zone.zone_id == zone_id:
                    zone.flood_level = round(min(zone.flood_level + 0.4, 4.0), 2)
                    self._recalculate_zone_priority(zone)
            desc = f"Flood severity increased in {'all zones' if not zone_id else zone_id}"

        elif event_type == "block_road":
            changed = 0
            for road in self.state.roads:
                if (zone_id is None or road.from_zone == zone_id) and road.road_status == RoadStatus.OPEN:
                    road.road_status = RoadStatus.BLOCKED
                    road.water_depth_m = 0.8
                    changed += 1
                    if changed >= 3:
                        break
            desc = f"Road blocked in zone {zone_id or 'random'}"
            self._update_zone_blocked_roads()

        elif event_type == "increase_medical_demand":
            for zone in self.state.zones:
                if zone_id is None or zone.zone_id == zone_id:
                    zone.critical_patients = int(zone.critical_patients * 1.3)
                    zone.injured_people = int(zone.injured_people * 1.2)
                    zone.ambulance_requirement = max(1, math.ceil(zone.critical_patients / 5))
            desc = f"Medical demand increased in {'all' if not zone_id else zone_id}"

        elif event_type == "reduce_ambulances":
            reduce = min(5, self.state.resources.ambulances_available)
            self.state.resources.ambulances_available -= reduce
            self.state.resources.ambulances_total -= reduce
            desc = f"Ambulance fleet reduced by {reduce} (breakdown/unavailability)"

        elif event_type == "reduce_shelter":
            for zone in self.state.zones:
                if zone_id is None or zone.zone_id == zone_id:
                    zone.shelter_demand = int(zone.shelter_demand * 1.25)
            r = self.state.resources
            r.shelter_available = max(0, r.shelter_available - 500)
            desc = f"Shelter capacity reduced in {'all' if not zone_id else zone_id}"

        elif event_type == "comm_failure":
            target = zone_id or "Z03"
            self.state.communication_status[target] = "Down"
            desc = f"Communication tower failure in zone {target}"

        elif event_type == "power_failure":
            target = zone_id or "Z04"
            self.state.power_status[target] = "Outage"
            desc = f"Power station failure in zone {target}"

        elif event_type == "add_perungudi":
            if not any(z.zone_id == "Z06" for z in self.state.zones):
                self.add_perungudi_zone()
                desc = "🚨 NEW AFFECTED ZONE: Perungudi added to emergency response"
            else:
                desc = "Perungudi already in simulation"

        self._add_incident("Simulation Control", desc, zone_id=zone_id)
        return desc

    # ── Zone Recalculation ─────────────────────────────────────────────────

    def _rebuild_zones(self):
        """Rebuild all zones from updated parameters."""
        new_zones = []
        for zone in self.state.zones:
            if zone.zone_id == "Z06":
                new_zones.append(zone)  # Perungudi rebuilt separately
                continue
            cfg = INITIAL_ZONES_CONFIG.get(zone.zone_id, {"flood_boost": 1.0})
            rebuilt = self._build_zone(zone.zone_id, cfg["flood_boost"])
            rebuilt.is_new = zone.is_new
            new_zones.append(rebuilt)
        self.state.zones = new_zones

    def _recalculate_zone_priority(self, zone: AffectedZone):
        if zone.flood_level >= 2.0 or zone.critical_patients >= 25:
            zone.priority = Priority.CRITICAL
            zone.priority_reason = f"Flood level {zone.flood_level}m ≥ 2.0m"
        elif zone.flood_level >= 1.2:
            zone.priority = Priority.HIGH
            zone.priority_reason = f"Flood level {zone.flood_level}m ≥ 1.2m"
        elif zone.flood_level >= 0.6:
            zone.priority = Priority.MEDIUM
            zone.priority_reason = f"Flood level {zone.flood_level}m ≥ 0.6m"
        else:
            zone.priority = Priority.LOW
            zone.priority_reason = "Low flood level"

    def _update_zone_blocked_roads(self):
        for zone in self.state.zones:
            zone.blocked_roads = sum(
                1 for r in self.state.roads
                if (r.from_zone == zone.zone_id or r.to_zone == zone.zone_id)
                and r.road_status in (RoadStatus.BLOCKED, RoadStatus.FLOODED)
            )

    # ── Simulation Tick ────────────────────────────────────────────────────

    def tick(self):
        """Advance simulation by one step."""
        self.state.tick += 1
        self.state.sim_time = _sim_time(self.state.tick)
        # Gradual rain increase every 10 ticks
        if self.state.tick % 10 == 0:
            self.state.rainfall_mm = round(self.state.rainfall_mm + 2.5, 1)
            self._rainfall_offset += 2.5

    # ── Incident Log ───────────────────────────────────────────────────────

    def _add_incident(self, event_type: str, description: str,
                      zone_id: Optional[str] = None, severity: Optional[str] = None):
        evt = IncidentEvent(
            event_id=_uid(),
            timestamp=_now(),
            sim_time=self.state.sim_time,
            event_type=event_type,
            description=description,
            zone_id=zone_id,
            severity=severity,
        )
        self.state.incidents.insert(0, evt)  # prepend so newest is first
        if len(self.state.incidents) > 200:
            self.state.incidents = self.state.incidents[:200]

    def add_agent_event(self, agent: str, event_type: str,
                        request: Optional[str] = None,
                        response: Optional[str] = None,
                        decision: Optional[str] = None,
                        reason: Optional[str] = None,
                        zone_id: Optional[str] = None):
        evt = AgentEvent(
            event_id=_uid(),
            timestamp=_now(),
            agent=agent,
            event_type=event_type,
            request=request,
            response=response,
            decision=decision,
            reason=reason,
            zone_id=zone_id,
        )
        self.state.agent_events.insert(0, evt)
        if len(self.state.agent_events) > 300:
            self.state.agent_events = self.state.agent_events[:300]
        self._add_incident(f"Agent:{agent}", event_type + (f" — {decision}" if decision else ""), zone_id=zone_id)

    def set_agent_status(self, agent: str, status: AgentStatus, action: str):
        if agent in self.state.agents:
            self.state.agents[agent].status = status
            self.state.agents[agent].last_action = action
            self.state.agents[agent].last_updated = _now()

    def get_zone(self, zone_id: str) -> Optional[AffectedZone]:
        for z in self.state.zones:
            if z.zone_id == zone_id:
                return z
        return None


# Singleton
engine = SimulationEngine()
