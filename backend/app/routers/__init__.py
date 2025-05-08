from app.routers.general import router as general_router
from app.routers.auth import router as auth_router
from app.routers.audio import router as audio_router
from app.routers.training import router as training_router
from app.routers.alerts import router as alerts_router

__all__ = [
    "general_router", 
    "auth_router", 
    "audio_router", 
    "training_router",
    "alerts_router"
]