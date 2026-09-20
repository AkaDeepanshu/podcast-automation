"""FastAPI entrypoint — wires routers and CORS."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import (
    assets,
    automation,
    config,
    discovery,
    jobs,
    notifications,
    ops,
    topics,
    ws,
)

app = FastAPI(title="Podcast Automation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(ws.router)
app.include_router(config.router)
app.include_router(assets.router)
app.include_router(topics.router)
app.include_router(automation.router)
app.include_router(notifications.router)
app.include_router(discovery.router)
app.include_router(ops.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    """Liveness probe. For readiness / ops checklist use GET /api/ops/status."""
    return {"status": "ok"}
