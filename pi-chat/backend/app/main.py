"""
PI Vision Chat Interface - FastAPI Backend
Main application entry point
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import chat, pi_system, admin, health


# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting PI Vision Chat Interface Backend...")

    # Initialize services
    try:
        # Import services here to avoid circular imports
        from app.services.af_sdk.client import AFSDKClient
        from app.services.vector_db.chroma_client import ChromaDBClient

        # Initialize AF SDK connection
        if settings.use_af_sdk:
            logger.info("Initializing AF SDK connection...")
            af_client = AFSDKClient()
            app.state.af_client = af_client
            logger.success("AF SDK initialized successfully")

        # Initialize Vector DB
        logger.info("Initializing Vector Database...")
        vector_db = ChromaDBClient()
        app.state.vector_db = vector_db
        logger.success("Vector Database initialized successfully")

        # Initialize LLM service
        from app.services.llm.ollama_client import OllamaClient
        logger.info("Initializing Ollama client...")
        ollama_client = OllamaClient()
        app.state.ollama = ollama_client
        logger.success("Ollama client initialized successfully")

        logger.success("All services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down PI Vision Chat Interface Backend...")
    if hasattr(app.state, 'af_client'):
        logger.info("Closing AF SDK connections...")
        # Cleanup AF SDK connections
    logger.success("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="PI Vision Chat Interface API",
    description="Backend API for PI Vision chat interface with LLM integration",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.enable_swagger else None,
    redoc_url="/api/redoc" if settings.enable_swagger else None,
)


# Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "message": "Request validation failed"
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred"
        }
    )


# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(pi_system.router, prefix="/api/pi", tags=["PI System"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "PI Vision Chat Interface API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs" if settings.enable_swagger else None
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_config=None,  # Use loguru instead
    )
