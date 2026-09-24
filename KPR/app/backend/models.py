"""
Core Pydantic models for the Chennai Flood Emergency Response Simulation.
These define the shape of all simulation state objects.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


# ─── Enums ────────────────────────────────────────────────────────────────────

class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Severity(str, Enum):
    CRITICAL = "Critical"
    SEVERE = "Severe"
    MODERATE = "Moderate"
    MINOR = "Minor"

class RoadStatus(str, Enum):
    OPEN = "Open"
    BLOCKED = "Blocked"
    FLOODED = "Flooded"

class AgentStatus(str, Enum):
    IDLE = "Idle"
    ANALYZING = "Analyzing"
    REQUESTING = "Requesting"
    REALLOCATING = "Reallocating"
    RESOLVING = "Resolving"
    CALCULATING = "Calculating"
    UPDATING = "Updating"
    READY = "Ready"

class SimulationStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"


# ─── Zone ─────────────────────────────────────────────────────────────────────

class AffectedZone(BaseModel):
    zone_id: str
    zone_name: str
    latitude: float
    longitude: float
    population: int
    population_at_risk: int
    flood_severity: str
    flood_level: float          # metres
    priority: Priority
    critical_patients: int
    injured_people: int
    vulnerable_population: int  # elderly/children
    blocked_roads: int
    shelter_demand: int
    food_requirement: int       # packets
    water_requirement: int      # litres
    ambulance_requirement: int
    rescue_vehicle_requirement: int
    medical_team_requirement: int
    is_new: bool = False        # True when added during live simulation
    added_at: Optional[str] = None
    priority_reason: str = ""


# ─── Resources ────────────────────────────────────────────────────────────────

class ResourcePool(BaseModel):
    # Vehicles
    ambulances_total: int = 0
    ambulances_available: int = 0
    ambulances_deployed: int = 0

    rescue_vehicles_total: int = 0
    rescue_vehicles_available: int = 0
    rescue_vehicles_deployed: int = 0

    helicopters_total: int = 0
    helicopters_available: int = 0
    helicopters_deployed: int = 0

    evacuation_vehicles_total: int = 0
    evacuation_vehicles_available: int = 0
    evacuation_vehicles_deployed: int = 0

    # Personnel
    police_units_total: int = 0
    police_units_available: int = 0
    police_units_deployed: int = 0

    medical_teams_total: int = 0
    medical_teams_available: int = 0
    medical_teams_deployed: int = 0

    # Supplies
    shelter_total: int = 0
    shelter_occupied: int = 0
    shelter_available: int = 0

    food_total: int = 0        # packets
    food_distributed: int = 0
    food_available: int = 0

    water_total: int = 0       # litres
    water_distributed: int = 0
    water_available: int = 0

    medical_supplies_total: int = 0  # kits
    medical_supplies_used: int = 0
    medical_supplies_available: int = 0

    fuel_total: int = 0        # litres
    fuel_used: int = 0
    fuel_available: int = 0


# ─── Allocations ──────────────────────────────────────────────────────────────

class ZoneAllocation(BaseModel):
    zone_id: str
    zone_name: str
    ambulances: int = 0
    rescue_vehicles: int = 0
    helicopters: int = 0
    police_units: int = 0
    medical_teams: int = 0
    evacuation_vehicles: int = 0
    shelter_slots: int = 0
    food_packets: int = 0
    water_litres: int = 0
    medical_kits: int = 0
    evacuation_routes: List[str] = []
    blocked_roads: List[str] = []
    allocation_reasons: Dict[str, str] = {}


# ─── Agents ───────────────────────────────────────────────────────────────────

class AgentState(BaseModel):
    name: str
    status: AgentStatus
    last_action: str
    last_updated: str
    requests: List[str] = []
    decisions: List[str] = []


class AgentEvent(BaseModel):
    event_id: str
    timestamp: str
    agent: str
    event_type: str
    request: Optional[str] = None
    response: Optional[str] = None
    decision: Optional[str] = None
    reason: Optional[str] = None
    zone_id: Optional[str] = None


# ─── Roads ────────────────────────────────────────────────────────────────────

class RoadLink(BaseModel):
    road_id: str
    from_zone: str
    to_zone: str
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    distance_km: float
    road_status: RoadStatus
    water_depth_m: float
    travel_time_min: float


class EvacuationRoute(BaseModel):
    route_id: str
    from_zone: str
    to_zone: str
    via: List[str]
    total_distance_km: float
    estimated_time_min: float
    status: str
    description: str


# ─── Response Plan ────────────────────────────────────────────────────────────

class ResponsePlan(BaseModel):
    plan_id: str
    version: int
    generated_at: str
    zones: List[AffectedZone]
    allocations: List[ZoneAllocation]
    resource_snapshot: ResourcePool
    evacuation_routes: List[EvacuationRoute]
    blocked_roads: List[str]
    unresolved_conflicts: List[str]
    coordinator_decisions: List[str]
    rationale: str
    public_alert: str
    what_changed: Optional[List[str]] = None  # populated for V2+


# ─── Incident Timeline ────────────────────────────────────────────────────────

class IncidentEvent(BaseModel):
    event_id: str
    timestamp: str
    sim_time: str
    event_type: str
    description: str
    zone_id: Optional[str] = None
    severity: Optional[str] = None


# ─── Simulation State ─────────────────────────────────────────────────────────

class SimulationState(BaseModel):
    status: SimulationStatus = SimulationStatus.IDLE
    speed: float = 1.0
    sim_time: str = "09:00"
    tick: int = 0
    rainfall_mm: float = 0.0
    overall_severity: str = "Moderate"
    zones: List[AffectedZone] = []
    resources: ResourcePool = ResourcePool()
    allocations: List[ZoneAllocation] = []
    agents: Dict[str, AgentState] = {}
    agent_events: List[AgentEvent] = []
    incidents: List[IncidentEvent] = []
    plans: List[ResponsePlan] = []
    current_plan_version: int = 0
    roads: List[RoadLink] = []
    evacuation_routes: List[EvacuationRoute] = []
    hospitals: List[Dict[str, Any]] = []
    shelters: List[Dict[str, Any]] = []
    communication_status: Dict[str, str] = {}
    power_status: Dict[str, str] = {}
    public_alert: Optional[str] = None
    alert_severity: Optional[str] = None
    demo_mode: bool = False
    demo_step: int = 0


# ─── API Request/Response ────────────────────────────────────────────────────

class SimControlRequest(BaseModel):
    speed: Optional[float] = None

class ManualEventRequest(BaseModel):
    event_type: str
    zone_id: Optional[str] = None
    parameters: Dict[str, Any] = {}

class AddZoneRequest(BaseModel):
    zone_id: str
    zone_name: str
    latitude: float
    longitude: float
    population: int
    flood_level: float
