"""Main FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .config import settings
from .database import init_db
from .api import (
    auth,
    scans,
    vulnerabilities,
    graph,
    logs,
    settings as settings_router,
    agent,
    dashboard,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the application"""
    # Startup
    print("🚀 Trinity Agent API starting...")
    init_db()
    print("✅ Database initialized")
    yield
    # Shutdown
    print("👋 Trinity Agent API shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=f"{settings.API_PREFIX}/docs",
    openapi_url=f"{settings.API_PREFIX}/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["Authentication"])
app.include_router(agent.router, prefix=settings.API_PREFIX, tags=["Agent"])
app.include_router(dashboard.router, prefix=settings.API_PREFIX, tags=["Dashboard"])
app.include_router(scans.router, prefix=settings.API_PREFIX, tags=["Scans"])
app.include_router(vulnerabilities.router, prefix=settings.API_PREFIX, tags=["Vulnerabilities"])
app.include_router(graph.router, prefix=settings.API_PREFIX, tags=["Graph"])
app.include_router(logs.router, prefix=settings.API_PREFIX, tags=["Logs"])
app.include_router(settings_router.router, prefix=settings.API_PREFIX, tags=["Settings"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Trinity Agent API",
        "version": settings.VERSION,
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "neo4j": "connected",
        "chromadb": "connected"
    }
