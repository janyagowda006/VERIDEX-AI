import os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, validate_jwt_secret_configuration
from app.api.routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Validates critical security configuration at application startup boundary.
    Fails fast if production configuration is invalid or insecure.
    """
    env = getattr(app.state, "ENVIRONMENT", None) or os.environ.get("ENVIRONMENT") or settings.ENVIRONMENT
    secret = getattr(app.state, "JWT_SECRET", None) or os.environ.get("JWT_SECRET") or settings.JWT_SECRET
    validate_jwt_secret_configuration(environment=env, secret=secret)
    yield


def create_app(
    environment: Optional[str] = None,
    jwt_secret: Optional[str] = None
) -> FastAPI:
    """
    Factory creating a configured FastAPI application instance.
    Useful for testing, production entrypoints, and startup verification.
    """
    @asynccontextmanager
    async def app_lifespan(app_inst: FastAPI):
        env = getattr(app_inst.state, "ENVIRONMENT", None) or environment or os.environ.get("ENVIRONMENT") or settings.ENVIRONMENT
        sec = getattr(app_inst.state, "JWT_SECRET", None) or jwt_secret or os.environ.get("JWT_SECRET") or settings.JWT_SECRET
        validate_jwt_secret_configuration(environment=env, secret=sec)
        yield

    app_instance = FastAPI(
        title=settings.PROJECT_NAME,
        description="Evidence-First AI Decision Intelligence Platform",
        version="0.1.0",
        lifespan=app_lifespan
    )

    if environment:
        app_instance.state.ENVIRONMENT = environment
    if jwt_secret:
        app_instance.state.JWT_SECRET = jwt_secret

    # Configure CORS Middleware (TASK-BE-01)
    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"]
    )

    # Include API routes
    app_instance.include_router(api_router)

    @app_instance.get("/")
    def root():
        """
        Root endpoint confirming service identity.
        """
        return {
            "project": settings.PROJECT_NAME,
            "message": "VERIDEX Backend Service Running",
            "phase": "Phase 1 - Project Foundation"
        }

    return app_instance


# Default application instance for uvicorn and module imports
app = create_app()
