"""
FastAPI application entry point.
"""
from fastapi import FastAPI, Request, status  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from fastapi.exceptions import RequestValidationError  # type: ignore
import logging

from app.config import settings  # type: ignore
from app.routes.auth import router as auth_router  # type: ignore
from app.routes.sos import router as sos_router  # type: ignore
from app.routes.quiz import router as quiz_router  # type: ignore
from app.routes.upload import router as upload_router  # type: ignore
from app.routes.mood import router as mood_router  # type: ignore
from app.routes.album import router as album_router  # type: ignore
from app.routes.care import router as care_router  # type: ignore
from app.routes.report import router as report_router  # type: ignore
from app.routes.routine import router as routine_router  # type: ignore
from firebase_admin.exceptions import FirebaseError # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create FastAPI application
app = FastAPI(
    title="AlzCareApp Authentication API",
    description="Secure authentication system with JWT and Firestore",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


class AuthError(Exception):
    def __init__(self, message: str):
        self.message = message

@app.exception_handler(FirebaseError)
async def firebase_exception_handler(request: Request, exc: FirebaseError):
    logger.error(f"Firebase error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database service unavailable", "message": str(exc)}
    )

@app.exception_handler(AuthError)
async def auth_exception_handler(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": exc.message}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    
    if settings.ENVIRONMENT == "development":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error": str(exc)
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"}
        )


# Include routers
app.include_router(auth_router)
app.include_router(sos_router)
app.include_router(quiz_router)
app.include_router(upload_router)
app.include_router(mood_router)
app.include_router(album_router)
app.include_router(care_router)
app.include_router(report_router)
app.include_router(routine_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AlzCareApp Authentication API",
        "version": "1.0.0",
        "docs": "/docs" if settings.ENVIRONMENT == "development" else "disabled"
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Log startup information."""
    logger.info("Starting AlzCareApp Authentication API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Allowed origins: {settings.allowed_origins_list}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information."""
    logger.info("Shutting down AlzCareApp Authentication API")


if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
