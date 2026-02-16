"""
AI Data Labs - Main API Application

FastAPI application with AI agent orchestration for data analytics.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import logging

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
from app.api.v1 import platforms, agents, data, monitoring

# Register routers
app.include_router(platforms.router, prefix="/api/v1/platforms", tags=["platforms"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])


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
