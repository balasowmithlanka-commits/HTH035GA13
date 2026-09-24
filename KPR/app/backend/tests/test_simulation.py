"""
Tests for Chennai Flood Emergency Response Simulation.
Tests verify resource constraints, agent decisions, and plan integrity.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from simulation_engine import SimulationEngine
from agents.coordinator_agent import CoordinatorAgent
from models import Priority, SimulationStatus, ZoneAllocation


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_engine():
    e = SimulationEngine()
    e.initialise()
    return e

@pytest.fixture
def engine_with_zones(fresh_engine):
    fresh_engine.build_initial_zones()
    fresh_engine.calculate_evacuation_routes()
    return fresh_engine

@pytest.fixture
def engine_with_plan(engine_with_zones):
    coord = CoordinatorAgent(engine_with_zones)
    coord.generate_plan()
    return engine_with_zones, coord


# ── Resource constraint tests ──────────────────────────────────────────────────

def test_resource_pool_initialized(fresh_engine):
    r = fresh_engine.state.resources
    assert r.ambulances_total > 0
    assert r.rescue_vehicles_total > 0
    assert r.helicopters_total > 0
    assert r.medical_teams_total > 0

def test_ambulances_available_lte_total(fresh_engine):
    r = fresh_engine.state.resources
    assert r.ambulances_available <= r.ambulances_total

def test_allocation_never_exceeds_pool(engine_with_plan):
    engine, coord = engine_with_plan
    r = engine.state.resources
    allocs = engine.state.allocations

    # Sum of all zone allocations must not exceed totals
    total_amb = sum(a.ambulances for a in allocs)
    total_rescue = sum(a.rescue_vehicles for a in allocs)
    total_heli = sum(a.helicopters for a in allocs)
    total_teams = sum(a.medical_teams for a in allocs)
    total_police = sum(a.police_units for a in allocs)

    assert total_amb <= r.ambulances_total, \
        f"Ambulance over-allocation: {total_amb} > {r.ambulances_total}"
    assert total_rescue <= r.rescue_vehicles_total, \
        f"Rescue over-allocation: {total_rescue} > {r.rescue_vehicles_total}"
    assert total_heli <= r.helicopters_total, \
        f"Helicopter over-allocation: {total_heli} > {r.helicopters_total}"
    assert total_teams <= r.medical_teams_total, \
        f"Medical team over-allocation: {total_teams} > {r.medical_teams_total}"
    assert total_police <= r.police_units_total, \
        f"Police over-allocation: {total_police} > {r.police_units_total}"

def test_resource_pool_decreases_after_allocation(engine_with_plan):
    engine, _ = engine_with_plan
    r = engine.state.resources
    # After allocation, deployed > 0 if any allocations made
    if engine.state.allocations:
        assert r.ambulances_deployed + r.ambulances_available == r.ambulances_total


# ── Zone tests ────────────────────────────────────────────────────────────────

def test_five_initial_zones(engine_with_zones):
    assert len(engine_with_zones.state.zones) == 5

def test_initial_zone_ids(engine_with_zones):
    zone_ids = {z.zone_id for z in engine_with_zones.state.zones}
    assert zone_ids == {"Z01", "Z02", "Z03", "Z04", "Z05"}

def test_zone_priority_is_valid(engine_with_zones):
    valid = {Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW}
    for zone in engine_with_zones.state.zones:
        assert zone.priority in valid

def test_zone_population_positive(engine_with_zones):
    for z in engine_with_zones.state.zones:
        assert z.population > 0
        assert z.population_at_risk > 0
        assert z.population_at_risk <= z.population

def test_perungudi_adds_sixth_zone(engine_with_zones):
    engine_with_zones.add_perungudi_zone()
    assert len(engine_with_zones.state.zones) == 6
    ids = {z.zone_id for z in engine_with_zones.state.zones}
    assert "Z06" in ids

def test_perungudi_is_marked_new(engine_with_zones):
    engine_with_zones.add_perungudi_zone()
    perungudi = next(z for z in engine_with_zones.state.zones if z.zone_id == "Z06")
    assert perungudi.is_new is True

def test_perungudi_priority_critical_or_high(engine_with_zones):
    engine_with_zones.add_perungudi_zone()
    perungudi = next(z for z in engine_with_zones.state.zones if z.zone_id == "Z06")
    assert perungudi.priority in (Priority.CRITICAL, Priority.HIGH)


# ── Agent tests ───────────────────────────────────────────────────────────────

def test_medical_agent_requests_per_zone(engine_with_zones):
    from agents.medical_agent import MedicalAgent
    med = MedicalAgent(engine_with_zones)
    requests = med.analyze(engine_with_zones.state.zones)
    assert len(requests) == len(engine_with_zones.state.zones)
    for zid, req in requests.items():
        assert req["ambulances"] >= 1
        assert req["medical_teams"] >= 1

def test_logistics_detects_conflict(engine_with_zones):
    from agents.medical_agent import MedicalAgent
    from agents.logistics_agent import LogisticsAgent
    r = engine_with_zones.state.resources
    # Force resource scarcity for test
    r.ambulances_available = 1
    med = MedicalAgent(engine_with_zones)
    log = LogisticsAgent(engine_with_zones)
    requests = med.analyze(engine_with_zones.state.zones)
    conflicts = log.detect_conflicts(requests, r)
    # With 5 zones needing at least 1 ambulance each and only 1 available, expect conflict
    assert len(conflicts) > 0

def test_routing_identifies_blocked_roads(engine_with_zones):
    from agents.routing_agent import RoutingAgent
    # Block some roads
    from models import RoadStatus
    for road in engine_with_zones.state.roads[:5]:
        road.road_status = RoadStatus.BLOCKED
    rout = RoutingAgent(engine_with_zones)
    report = rout.assess_roads(engine_with_zones.state.roads)
    assert report["blocked"] >= 5


# ── Plan tests ────────────────────────────────────────────────────────────────

def test_plan_v1_generated(engine_with_plan):
    engine, _ = engine_with_plan
    assert len(engine.state.plans) == 1
    assert engine.state.plans[0].version == 1

def test_plan_has_all_zones_covered(engine_with_plan):
    engine, _ = engine_with_plan
    plan = engine.state.plans[0]
    zone_ids = {z.zone_id for z in plan.zones}
    alloc_ids = {a.zone_id for a in plan.allocations}
    assert zone_ids == alloc_ids

def test_plan_v2_differs_from_v1(engine_with_zones):
    coord = CoordinatorAgent(engine_with_zones)
    plan_v1 = coord.generate_plan()

    # Add Perungudi to trigger replan
    engine_with_zones.add_perungudi_zone()
    # Reset deployments for fresh allocation
    r = engine_with_zones.state.resources
    r.ambulances_deployed = 0
    r.ambulances_available = r.ambulances_total
    r.helicopters_deployed = 0
    r.helicopters_available = r.helicopters_total
    r.rescue_vehicles_deployed = 0
    r.rescue_vehicles_available = r.rescue_vehicles_total
    r.medical_teams_deployed = 0
    r.medical_teams_available = r.medical_teams_total

    plan_v2 = coord.generate_plan()
    assert plan_v2.version == 2
    assert len(plan_v2.zones) == 6
    assert len(plan_v1.zones) == 5
    assert plan_v2.what_changed is not None
    assert len(plan_v2.what_changed) > 0

def test_what_changed_includes_new_zone(engine_with_zones):
    coord = CoordinatorAgent(engine_with_zones)
    coord.generate_plan()
    engine_with_zones.add_perungudi_zone()
    r = engine_with_zones.state.resources
    r.ambulances_deployed = 0
    r.ambulances_available = r.ambulances_total
    r.helicopters_deployed = 0
    r.helicopters_available = r.helicopters_total
    r.rescue_vehicles_deployed = 0
    r.rescue_vehicles_available = r.rescue_vehicles_total
    r.medical_teams_deployed = 0
    r.medical_teams_available = r.medical_teams_total
    plan_v2 = coord.generate_plan()
    changes_text = " ".join(plan_v2.what_changed or [])
    assert "Perungudi" in changes_text


# ── Event propagation tests ───────────────────────────────────────────────────

def test_rainfall_event_increases_rain(engine_with_zones):
    before = engine_with_zones.state.rainfall_mm
    engine_with_zones.apply_manual_event("increase_rainfall", params={"delta": 20})
    assert engine_with_zones.state.rainfall_mm >= before + 20

def test_road_block_event_affects_roads(engine_with_zones):
    from models import RoadStatus
    before_blocked = sum(1 for r in engine_with_zones.state.roads if r.road_status != RoadStatus.OPEN)
    engine_with_zones.apply_manual_event("block_road", zone_id="Z04")
    after_blocked = sum(1 for r in engine_with_zones.state.roads if r.road_status != RoadStatus.OPEN)
    assert after_blocked >= before_blocked

def test_comm_failure_event(engine_with_zones):
    engine_with_zones.apply_manual_event("comm_failure", zone_id="Z03")
    assert engine_with_zones.state.communication_status.get("Z03") == "Down"

def test_power_failure_event(engine_with_zones):
    engine_with_zones.apply_manual_event("power_failure", zone_id="Z04")
    assert engine_with_zones.state.power_status.get("Z04") == "Outage"


# ── Incident timeline tests ───────────────────────────────────────────────────

def test_incidents_logged_on_zone_add(engine_with_zones):
    before = len(engine_with_zones.state.incidents)
    engine_with_zones.add_perungudi_zone()
    assert len(engine_with_zones.state.incidents) > before

def test_incidents_have_required_fields(engine_with_zones):
    for inc in engine_with_zones.state.incidents:
        assert inc.event_id
        assert inc.timestamp
        assert inc.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
