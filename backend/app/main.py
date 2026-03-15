"""Main FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis

from .config import settings
from .database import init_db
from .services.vector_service import VectorService
from .api import (
    auth,
    scans,
    vulnerabilities,
    graph,
    logs,
    settings as settings_router,
    cves,
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

    # Startup sanity checks for dependent services used by autonomous workflows.
    try:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        if redis_client.ping():
            print("✅ Redis reachable")
    except Exception as exc:
        print(f"⚠️ Redis check failed: {exc}")

    try:
        vector_service = VectorService()
        if vector_service.collection is not None:
            count = vector_service.collection.count()
            print(f"✅ ChromaDB reachable, CVE records available: {count}")

            # If the collection is empty, seed a small curated baseline so
            # enrichment workflows have something to retrieve immediately.
            if count == 0:
                try:
                    added = await vector_service.seed_demo_cves(reset=False)
                    print(f"✅ Seeded demo CVEs on startup: {added}")
                except Exception as seed_exc:
                    print(f"⚠️ ChromaDB auto-seed skipped: {seed_exc}")
        else:
            print("⚠️ ChromaDB not available; fallback CVE data will be used")
    except Exception as exc:
        print(f"⚠️ ChromaDB startup check failed: {exc}")

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
    allow_origins=settings.CORS_ORIGINS_LIST,
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
app.include_router(cves.router, prefix=settings.API_PREFIX, tags=["CVEs"])


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
