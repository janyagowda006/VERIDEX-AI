from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Evidence-First AI Decision Intelligence Platform",
    version="0.1.0"
)

# Include API routes
app.include_router(api_router)


@app.get("/")
def root():
    """
    Root endpoint confirming service identity.
    """
    return {
        "project": settings.PROJECT_NAME,
        "message": "VERIDEX Backend Service Running",
        "phase": "Phase 1 - Project Foundation"
    }
