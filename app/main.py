"""
AI Data Labs - Main API Application

FastAPI application with AI agent orchestration for data analytics.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import logging
import time

# Import metrics
from app.core.metrics import (
    MetricsContext, initialize_metrics, start_metrics_server
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Data Labs API",
    description="AI-driven data infrastructure platform",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    """Middleware to monitor all HTTP requests."""
    method = request.method
    path = request.url.path

    # Skip health checks and metrics from detailed monitoring
    if path in ["/health", "/health/ready", "/health/live", "/metrics"]:
        return await call_next(request)

    with MetricsContext(method, path):
        response = await call_next(request)
    return response


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting AI Data Labs API...")
    # Initialize database connections
    # Initialize AI agents
    # Initialize monitoring
    logger.info("API ready to serve requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down AI Data Labs API...")
    # Close database connections
    # Cleanup AI agents
    logger.info("API shutdown complete")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "ai-data-labs-api"
    }


# Import routers
from app.api.v1 import platforms, agents, data, monitoring, schema, chat
from app.auth import router as auth_router
from app.agents import registry

# Register routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(platforms.router, prefix="/api/v1/platforms", tags=["platforms"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])
app.include_router(schema.router, prefix="/api/v1/schema", tags=["schema"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting AI Data Labs API...")

    # Initialize metrics
    try:
        import os
        build_version = os.getenv("BUILD_VERSION", "0.1.0")
        git_commit = os.getenv("GIT_COMMIT", "dev")
        initialize_metrics(build_version=build_version, git_commit=git_commit)
        logger.info("Metrics initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize metrics: {e}")

    # Initialize AI agents
    try:
        await registry.initialize_all()
        logger.info(f"Initialized {len(registry.get_all())} AI agents")
    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}")

    logger.info("API ready to serve requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down AI Data Labs API...")

    # Shutdown AI agents
    try:
        await registry.shutdown_all()
    except Exception as e:
        logger.error(f"Error shutting down agents: {e}")

    logger.info("API shutdown complete")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Data Labs - AI-Driven Data Infrastructure",
        "version": "0.1.0",
        "docs": "/api/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
