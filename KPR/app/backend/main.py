"""
Chennai Flood Emergency Response — FastAPI Backend
===================================================
Real-time multi-agent disaster response coordination system.
"""
import asyncio
import json
import os
from typing import List, Optional, Set
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from models import (
    SimulationState, SimControlRequest, ManualEventRequest, AddZoneRequest,
    SimulationStatus, ResponsePlan, AffectedZone
)
from simulation_engine import engine
from agents.coordinator_agent import CoordinatorAgent
from demo_controller import DemoController

# ─── App setup ────────────────────────────────────────────────────────────────

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(
    title="Chennai Flood Emergency Response API",
    description="Multi-Agent Disaster Response Coordinator",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, data: dict):
        import json as _json
        raw = _json.dumps(data)
        raw = raw.replace(': NaN', ': null').replace(':NaN', ':null')
        raw = raw.replace(': Infinity', ': null').replace(':Infinity', ':null')
        dead = set()
        for ws in self.active_connections:
            try:
                await ws.send_text(raw)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active_connections.discard(ws)


manager = ConnectionManager()
coordinator = CoordinatorAgent(engine)
demo_ctrl: Optional[DemoController] = None
sim_task: Optional[asyncio.Task] = None


async def broadcast_state():
    """Broadcast the full simulation state to all connected clients."""
    state_dict = engine.state.model_dump()
    await manager.broadcast({"type": "state", "payload": state_dict})


# ─── Simulation loop ──────────────────────────────────────────────────────────

async def simulation_loop():
    """Background task that advances simulation ticks."""
    while engine.state.status == SimulationStatus.RUNNING:
        engine.tick()
        await broadcast_state()
        speed = engine.state.speed
        await asyncio.sleep(max(0.1, 2.0 / speed))


# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    engine.initialise()


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current state immediately on connect
        await websocket.send_json({"type": "state", "payload": engine.state.model_dump()})
        while True:
            # Keep connection alive; client sends pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ─── Simulation control ───────────────────────────────────────────────────────

@app.post("/api/simulation/start")
async def start_simulation(req: SimControlRequest = SimControlRequest(), background_tasks: BackgroundTasks = None):
    global sim_task
    if req.speed:
        engine.state.speed = req.speed

    if engine.state.status == SimulationStatus.IDLE:
        engine.build_initial_zones()
        engine.calculate_evacuation_routes()
        engine._add_incident("System", "Simulation started — 5 zones active")

    engine.state.status = SimulationStatus.RUNNING
    if sim_task and not sim_task.done():
        sim_task.cancel()
    sim_task = asyncio.create_task(simulation_loop())
    await broadcast_state()
    return {"status": "running", "zones": len(engine.state.zones)}


@app.post("/api/simulation/pause")
async def pause_simulation():
    engine.state.status = SimulationStatus.PAUSED
    if sim_task:
        sim_task.cancel()
    engine._add_incident("System", "Simulation paused")
    await broadcast_state()
    return {"status": "paused"}


@app.post("/api/simulation/resume")
async def resume_simulation():
    global sim_task
    engine.state.status = SimulationStatus.RUNNING
    sim_task = asyncio.create_task(simulation_loop())
    engine._add_incident("System", "Simulation resumed")
    await broadcast_state()
    return {"status": "running"}


@app.post("/api/simulation/reset")
async def reset_simulation():
    global sim_task, demo_ctrl
    if sim_task:
        sim_task.cancel()
    engine.__init__()
    engine.initialise()
    demo_ctrl = None
    await broadcast_state()
    return {"status": "reset"}


@app.post("/api/simulation/speed")
async def set_speed(req: SimControlRequest):
    if req.speed:
        engine.state.speed = req.speed
    await broadcast_state()
    return {"speed": engine.state.speed}


# ─── Plan generation ──────────────────────────────────────────────────────────

@app.post("/api/plan/generate")
async def generate_plan():
    if not engine.state.zones:
        engine.build_initial_zones()
        engine.calculate_evacuation_routes()
    plan = coordinator.generate_plan()
    await broadcast_state()
    return plan.model_dump()


# ─── Demo mode ───────────────────────────────────────────────────────────────

@app.post("/api/demo/start")
async def start_demo():
    global demo_ctrl, sim_task
    if sim_task and not sim_task.done():
        sim_task.cancel()

    engine.__init__()
    engine.initialise()
    engine.state.speed = 1.0

    demo_ctrl = DemoController(engine, broadcast_state)
    asyncio.create_task(demo_ctrl.run_demo())
    return {"status": "demo_started"}


@app.get("/api/demo/step")
async def get_demo_step():
    return {
        "current_step": demo_ctrl.current_step if demo_ctrl else 0,
        "running": demo_ctrl.running if demo_ctrl else False,
    }


# ─── Manual events ────────────────────────────────────────────────────────────

@app.post("/api/events")
async def apply_event(req: ManualEventRequest):
    desc = engine.apply_manual_event(req.event_type, req.zone_id, req.parameters)
    await broadcast_state()
    return {"status": "applied", "description": desc}


# ─── Data endpoints ───────────────────────────────────────────────────────────

@app.get("/api/zones")
async def get_zones():
    return [z.model_dump() for z in engine.state.zones]


@app.post("/api/zones")
async def add_zone(req: AddZoneRequest):
    existing = engine.get_zone(req.zone_id)
    if existing:
        raise HTTPException(400, f"Zone {req.zone_id} already exists")
    zone = engine._build_zone(
        zone_id=req.zone_id,
        flood_boost=1.5,
        is_new=True,
        custom={
            "zone_name": req.zone_name,
            "latitude": req.latitude,
            "longitude": req.longitude,
            "population": req.population,
        }
    )
    engine.state.zones.append(zone)
    await broadcast_state()
    return zone.model_dump()


@app.get("/api/resources")
async def get_resources():
    return engine.state.resources.model_dump()


@app.get("/api/agents")
async def get_agents():
    return {name: agent.model_dump() for name, agent in engine.state.agents.items()}


@app.get("/api/plan/current")
async def get_current_plan():
    if not engine.state.plans:
        raise HTTPException(404, "No plan generated yet")
    return engine.state.plans[-1].model_dump()


@app.get("/api/plan/history")
async def get_plan_history():
    return [{"plan_id": p.plan_id, "version": p.version, "generated_at": p.generated_at,
             "zone_count": len(p.zones), "changes": len(p.what_changed or [])}
            for p in engine.state.plans]


@app.get("/api/plan/v/{version}")
async def get_plan_version(version: int):
    plan = next((p for p in engine.state.plans if p.version == version), None)
    if not plan:
        raise HTTPException(404, f"Plan V{version} not found")
    return plan.model_dump()


@app.get("/api/incidents")
async def get_incidents(limit: int = 50):
    return [i.model_dump() for i in engine.state.incidents[:limit]]


@app.get("/api/map")
async def get_map_data():
    return {
        "zones": [z.model_dump() for z in engine.state.zones],
        "roads": [r.model_dump() for r in engine.state.roads[:200]],
        "evacuation_routes": [r.model_dump() for r in engine.state.evacuation_routes],
        "hospitals": engine.state.hospitals,
        "allocations": [a.model_dump() for a in engine.state.allocations],
    }


@app.get("/api/alerts")
async def get_alerts():
    return {
        "severity": engine.state.alert_severity,
        "text": engine.state.public_alert,
        "zones": len(engine.state.zones),
        "critical_zones": sum(1 for z in engine.state.zones if z.priority.value == "CRITICAL"),
    }


@app.get("/api/state")
async def get_full_state():
    import json, math
    data = engine.state.model_dump()
    # Sanitize NaN/Inf values that break JSON spec
    raw = json.dumps(data)
    raw = raw.replace(': NaN', ': null').replace(':NaN', ':null')
    raw = raw.replace(': Infinity', ': null').replace(':Infinity', ':null')
    from fastapi.responses import Response
    return Response(content=raw, media_type="application/json")


@app.get("/api/health")
async def health():
    return {"status": "ok", "zones": len(engine.state.zones), "plans": len(engine.state.plans)}


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the command-center dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
