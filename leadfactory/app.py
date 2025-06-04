"""
Main FastAPI application for LeadFactory services.

Provides REST API endpoints for payment processing, IP rotation management,
and audit report delivery.
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from leadfactory.api.ip_rotation_api import router as ip_rotation_router
from leadfactory.api.payment_api import router as payment_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}',
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting LeadFactory API application")
    yield
    logger.info("Shutting down LeadFactory API application")


# Create FastAPI application
app = FastAPI(
    title="LeadFactory API",
    description="REST API for lead generation, payment processing, and audit delivery",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
        },
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Application health check."""
    return {"status": "healthy", "application": "leadfactory-api", "version": "1.0.0"}


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "LeadFactory API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# Include routers
app.include_router(payment_router)
app.include_router(ip_rotation_router)


# Checkout page routes
@app.get("/checkout")
async def checkout_page():
    """Serve the checkout page."""
    return FileResponse("leadfactory/static/checkout.html")


@app.get("/checkout/success")
async def checkout_success():
    """Serve the checkout success page."""
    return FileResponse("leadfactory/static/success.html")


@app.get("/checkout/cancel")
async def checkout_cancel():
    """Serve the checkout cancel/failure page."""
    return FileResponse("leadfactory/static/cancel.html")


# Mount static files
app.mount("/static", StaticFiles(directory="leadfactory/static"), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")  # Default to localhost for security

    uvicorn.run(
        "leadfactory.app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",  # nosec B104
    )
