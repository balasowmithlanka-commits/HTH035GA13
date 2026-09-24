"""
Demo Mode Controller
====================
Executes a deterministic demo scenario so the same presentation can be repeated.

Steps:
  1  → Start simulation, load zones
  2  → Show 5 affected zones with resources
  3  → Agents analyse the situation
  4  → Coordinator generates Plan V1
  5  → [delay] Perungudi flood event triggered
  6  → Agents react
  7  → Resource conflict detected
  8  → Agents negotiate
  9  → Coordinator generates Plan V2
  10 → What Changed shown
  11 → Map updated
  12 → Alert updated
  13 → Final state shown
"""
import asyncio
from typing import Callable, Awaitable
from simulation_engine import SimulationEngine, engine as _engine
from agents.coordinator_agent import CoordinatorAgent
from models import SimulationStatus, AgentStatus, Priority


class DemoController:

    def __init__(self, eng: SimulationEngine, broadcast_fn: Callable[[], Awaitable[None]]):
        self.engine = eng
        self.broadcast = broadcast_fn
        self.coordinator = CoordinatorAgent(eng)
        self.running = False
        self.current_step = 0

    async def _pause(self, seconds: float):
        """Delay between demo steps."""
        speed = self.engine.state.speed
        await asyncio.sleep(seconds / max(speed, 0.1))

    async def run_demo(self):
        """Execute the full demo scenario."""
        self.running = True
        self.engine.state.demo_mode = True
        self.engine.state.status = SimulationStatus.RUNNING
        st = self.engine.state

        # ── Step 1: Initialise ─────────────────────────────────────────────
        self.current_step = 1
        self.engine._add_incident("Demo", "STEP 1: Chennai flood scenario initiated")
        await self.broadcast()
        await self._pause(1.5)

        # ── Step 2: Build 5 zones ─────────────────────────────────────────
        self.current_step = 2
        self.engine.build_initial_zones()
        self.engine._add_incident("Demo",
            "STEP 2: 5 affected zones identified — North Chennai, Central Chennai, "
            "Adyar, Velachery, South-West Chennai"
        )
        self.engine.state.sim_time = "09:07"
        await self.broadcast()
        await self._pause(2)

        # ── Step 3: Agent analysis ─────────────────────────────────────────
        self.current_step = 3
        self.engine._add_incident("Demo", "STEP 3: All agents begin situation assessment")
        self.engine.set_agent_status("Medical", AgentStatus.ANALYZING, "Assessing critical patient load")
        self.engine.set_agent_status("Logistics", AgentStatus.ANALYZING, "Auditing resource inventory")
        self.engine.set_agent_status("Routing", AgentStatus.CALCULATING, "Mapping road network")
        self.engine.set_agent_status("Rescue", AgentStatus.ANALYZING, "Evaluating rescue requirements")
        self.engine.set_agent_status("Communication", AgentStatus.UPDATING, "Preparing initial alert")
        self.engine.state.sim_time = "09:12"
        await self.broadcast()
        await self._pause(2.5)

        # ── Step 4: Plan V1 ───────────────────────────────────────────────
        self.current_step = 4
        self.engine.state.sim_time = "09:18"
        self.engine._add_incident("Demo", "STEP 4: Coordinator generating Plan V1")
        self.engine.set_agent_status("Coordinator", AgentStatus.RESOLVING, "Creating initial response plan")
        await self.broadcast()

        plan_v1 = self.coordinator.generate_plan()
        self.engine._add_incident("Demo",
            f"Plan V1 generated — {len(plan_v1.zones)} zones | "
            f"{len(plan_v1.coordinator_decisions)} decisions | "
            f"Alert: {self.engine.state.alert_severity}"
        )
        await self.broadcast()
        await self._pause(3)

        # ── Step 5: Perungudi event ────────────────────────────────────────
        self.current_step = 5
        self.engine.state.sim_time = "09:23"
        self.engine._add_incident("Demo",
            "🚨 STEP 5: NEW AFFECTED ZONE DETECTED — PERUNGUDI FLOODING",
            zone_id="Z06", severity="Critical"
        )
        self.engine.apply_manual_event("increase_rainfall", params={"delta": 35.0})
        perungudi_zone = self.engine.add_perungudi_zone()
        await self.broadcast()
        await self._pause(2)

        # ── Step 6: Agents react ──────────────────────────────────────────
        self.current_step = 6
        self.engine.state.sim_time = "09:24"
        self.engine._add_incident("Demo", "STEP 6: Agents reassessing with Perungudi added")
        self.engine.set_agent_status("Medical", AgentStatus.ANALYZING,
                                     f"Reassessing — Perungudi has {perungudi_zone.critical_patients} critical patients")
        self.engine.set_agent_status("Logistics", AgentStatus.REALLOCATING,
                                     "Checking resource availability for 6 zones")
        self.engine.set_agent_status("Routing", AgentStatus.CALCULATING,
                                     "Recalculating routes — OMR road status unknown")
        self.engine.set_agent_status("Rescue", AgentStatus.REQUESTING,
                                     f"Helicopter request for Perungudi — {perungudi_zone.blocked_roads} roads blocked")
        await self.broadcast()
        await self._pause(2)

        # ── Step 7: Conflict ──────────────────────────────────────────────
        self.current_step = 7
        self.engine.state.sim_time = "09:24"
        r = self.engine.state.resources
        self.engine.add_agent_event(
            "Medical", "Resource conflict detected",
            request=f"Requesting {perungudi_zone.ambulance_requirement} ambulances for Perungudi",
            response=f"Only {r.ambulances_available} ambulances remain after V1 allocation",
            reason=f"Perungudi CRITICAL priority with {perungudi_zone.critical_patients} critical patients — insufficient ambulances",
            zone_id="Z06"
        )
        self.engine.add_agent_event(
            "Logistics", "Conflict: ambulance pool exhausted",
            request=f"Need {perungudi_zone.ambulance_requirement} more ambulances",
            response=f"Available: {r.ambulances_available}. Must reallocate from lower-priority zones.",
            decision="Propose reallocating 1-2 ambulances from MEDIUM zones to Perungudi",
            zone_id="Z06"
        )
        self.engine._add_incident("Demo",
            f"STEP 7: Resource conflict — Perungudi needs {perungudi_zone.ambulance_requirement} ambulances, "
            f"only {r.ambulances_available} available"
        )
        await self.broadcast()
        await self._pause(2)

        # ── Step 8: Negotiation ───────────────────────────────────────────
        self.current_step = 8
        self.engine.state.sim_time = "09:25"
        self.engine.set_agent_status("Coordinator", AgentStatus.RESOLVING,
                                     "Negotiating resource reallocation between zones")
        self.engine.add_agent_event(
            "Coordinator", "Negotiation: Perungudi resource allocation",
            request=f"Routing Agent: OMR partially blocked — helicopter deployment recommended for Perungudi",
            response=f"Medical Agent confirms {perungudi_zone.critical_patients} critical patients. "
                     f"Logistics confirms {r.ambulances_available} ambulances remain.",
            decision=(
                f"APPROVED: Deploy {min(2, r.helicopters_available)} helicopter(s) to Perungudi. "
                f"Reallocate ambulances from MEDIUM zones. "
                f"Perungudi receives CRITICAL priority allocation."
            ),
            reason=(
                f"Perungudi: CRITICAL priority, {perungudi_zone.flood_level}m flood, "
                f"{perungudi_zone.critical_patients} critical patients, {perungudi_zone.blocked_roads} blocked roads."
            ),
            zone_id="Z06"
        )
        self.engine._add_incident("Demo",
            "STEP 8: Coordinator negotiation complete — helicopter approved, reallocation planned"
        )
        await self.broadcast()
        await self._pause(2)

        # ── Step 9: Plan V2 ───────────────────────────────────────────────
        self.current_step = 9
        self.engine.state.sim_time = "09:26"
        self.engine._add_incident("Demo", "STEP 9: Coordinator generating Plan V2")
        # Reset resources to allow fresh reallocation
        self.engine.state.resources.ambulances_deployed = 0
        self.engine.state.resources.ambulances_available = self.engine.state.resources.ambulances_total
        self.engine.state.resources.rescue_vehicles_deployed = 0
        self.engine.state.resources.rescue_vehicles_available = self.engine.state.resources.rescue_vehicles_total
        self.engine.state.resources.helicopters_deployed = 0
        self.engine.state.resources.helicopters_available = self.engine.state.resources.helicopters_total
        self.engine.state.resources.medical_teams_deployed = 0
        self.engine.state.resources.medical_teams_available = self.engine.state.resources.medical_teams_total

        plan_v2 = self.coordinator.generate_plan()
        self.engine._add_incident("Demo",
            f"Plan V2 generated — now covers {len(plan_v2.zones)} zones | "
            f"{len(plan_v2.what_changed or [])} changes from V1"
        )

        # ── Step 10-13: Final updates ──────────────────────────────────────
        self.current_step = 10
        self.engine.state.sim_time = "09:27"
        self.engine._add_incident("Demo",
            f"STEP 10-13: What Changed populated ({len(plan_v2.what_changed or [])} items). "
            "Map updated. Alert updated. Final state displayed."
        )
        self.engine.set_agent_status("Coordinator", AgentStatus.READY,
                                     "Plan V2 active — all agents standing by")
        await self.broadcast()
        await self._pause(1)

        self.engine.state.demo_mode = True
        self.engine.state.demo_step = 13
        self.running = False
        await self.broadcast()
