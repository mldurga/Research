"""
Health check endpoints
"""

from fastapi import APIRouter, Request
from loguru import logger

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pi-vision-chat-backend",
        "version": "1.0.0"
    }


@router.get("/health/detailed")
async def detailed_health_check(request: Request):
    """Detailed health check with service status"""
    health_status = {
        "status": "healthy",
        "service": "pi-vision-chat-backend",
        "version": "1.0.0",
        "components": {}
    }

    # Check AF SDK connection
    try:
        if hasattr(request.app.state, 'af_client'):
            af_client = request.app.state.af_client
            health_status["components"]["af_sdk"] = {
                "status": "connected",
                "server": af_client.af_server.Name if af_client.af_server else "unknown"
            }
        else:
            health_status["components"]["af_sdk"] = {
                "status": "not_initialized"
            }
    except Exception as e:
        health_status["components"]["af_sdk"] = {
            "status": "error",
            "error": str(e)
        }

    # Check Vector DB
    try:
        if hasattr(request.app.state, 'vector_db'):
            vector_db = request.app.state.vector_db
            stats = vector_db.get_collection_stats()
            health_status["components"]["vector_db"] = {
                "status": "connected",
                "documents": stats.get("count", 0)
            }
        else:
            health_status["components"]["vector_db"] = {
                "status": "not_initialized"
            }
    except Exception as e:
        health_status["components"]["vector_db"] = {
            "status": "error",
            "error": str(e)
        }

    # Check Ollama
    try:
        if hasattr(request.app.state, 'ollama'):
            ollama = request.app.state.ollama
            models = await ollama.list_models()
            health_status["components"]["ollama"] = {
                "status": "connected",
                "models": len(models)
            }
        else:
            health_status["components"]["ollama"] = {
                "status": "not_initialized"
            }
    except Exception as e:
        health_status["components"]["ollama"] = {
            "status": "error",
            "error": str(e)
        }

    # Set overall status
    component_statuses = [
        comp["status"] for comp in health_status["components"].values()
    ]
    if "error" in component_statuses:
        health_status["status"] = "degraded"

    return health_status
