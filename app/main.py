import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.scheduler import AutonomousScheduler
from app.api.routes_leads import router as leads_router
from app.api.routes_deals import router as deals_router
from app.api.routes_settings import router as settings_router
from app.api.routes_stats import router as stats_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("omnilead.main")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        for dc in dead_connections:
            self.active_connections.discard(dc)

manager = ConnectionManager()

# Global Scheduler Instance
scheduler = AutonomousScheduler(broadcast_fn=manager.broadcast)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing OmniLead Database...")
    await init_db()
    logger.info("Starting Autonomous 24/7 Agent Scheduler...")
    scheduler.start()
    
    # Run an initial hunt cycle on startup in background if database has few leads
    asyncio.create_task(scheduler.run_hunt_cycle())

    yield

    # Shutdown
    logger.info("Shutting down OmniLead Agent...")
    scheduler.stop()

app = FastAPI(
    title=f"{settings.AGENT_NAME} API",
    description="24/7 Autonomous Lead Hunter & Deal Closer System",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(leads_router)
app.include_router(deals_router)
app.include_router(settings_router)
app.include_router(stats_router)

@app.post("/api/scan_now")
async def trigger_scan():
    """Trigger an instant lead hunting cycle immediately"""
    asyncio.create_task(scheduler.run_hunt_cycle())
    return {"status": "started", "message": "Instant lead hunting cycle launched in background"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Heartbeat ping/pong or client action
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Mount Static Dashboard Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(os.path.join(static_dir, "index.html"))
