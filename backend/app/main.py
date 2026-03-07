import logging
import os

from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.db.base import init_db
from app.routers import projects, documents, chats, admin
from app.services.chat_service import ServiceUnavailableError

# ---------------------------------------------------------------------------
# Logging — configure *before* any application code so every module that
# calls ``logging.getLogger(__name__)`` inherits a usable handler.
# ---------------------------------------------------------------------------

# Load Application Config
_settings = get_settings()
logging.root.setLevel(getattr(logging, _settings.log_level.upper(), logging.INFO))

logging.basicConfig(
    level=_settings.log_level.upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
# Reduce noise from chatty libraries; keep our app at INFO.
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Friendly labels for common HTTP status codes used in error responses.
_HTTP_ERROR_LABELS: dict[int, str] = {
    400: "Bad request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    422: "Validation error",
    429: "Too many requests",
    500: "Internal server error",
    502: "Bad gateway",
    503: "Service unavailable",
}

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    raise ValueError("DATABASE_URL not set.")

init_db(DATABASE_URL)

app = FastAPI(
    title="Research Assist AI",
    description="AI-powered research paper Q&A system",
    version="0.1.0",
)

# CORS configuration — loaded from settings (CORS_ORIGINS env var)

_cors_kwargs: dict = {
    "allow_methods": ["*"],
    "allow_headers": ["*"],
    "allow_credentials": True,
    "allow_origins": _settings.cors_origins,
}
# In local / dev, also accept any localhost port so CORS never blocks dev work.
if _settings.environment in ("local", "dev"):
    _cors_kwargs["allow_origin_regex"] = r"^https?://localhost(:\d+)?$"

app.add_middleware(CORSMiddleware, **_cors_kwargs)  # type: ignore[arg-type]

# Include routers
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(documents.projects_router)
app.include_router(chats.router)
app.include_router(admin.router)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 422 with a structured error body instead of FastAPI's default."""
    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content={
            "error": "Validation error",
            "message": "The request contains invalid or missing fields.",
            "details": {"validation_errors": exc.errors()},
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return a consistent JSON envelope for all HTTP errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": _HTTP_ERROR_LABELS.get(exc.status_code, "Error"),
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "details": None,
        },
    )


@app.exception_handler(ServiceUnavailableError)
async def service_unavailable_handler(request: Request, exc: ServiceUnavailableError) -> JSONResponse:
    """Map ServiceUnavailableError to 503."""
    logger.error("Service unavailable: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Service unavailable",
            "message": str(exc),
            "details": None,
        },
    )


@app.exception_handler(EndpointConnectionError)
@app.exception_handler(ClientError)
async def aws_client_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map unrecoverable AWS client errors to 503 Service Unavailable."""
    logger.error("AWS service error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Service unavailable",
            "message": "An upstream AWS service is temporarily unavailable. Please try again.",
            "details": None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — return 500 without leaking stack traces."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected internal error occurred. Please contact support if the problem persists.",
            "details": None,
        },
    )


@app.get("/api/health")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "research-assist-ai-backend",
        "version": "0.1.0",
        "environment": settings.environment,
        "config_loaded": True,
    }


@app.get("/api/config")
async def get_config_info(settings: Settings = Depends(get_settings)):
    """Get current configuration (non-sensitive values only)"""
    return {
        "chunking": {
            "strategy": settings.chunking.strategy,
            "chunk_size_tokens": settings.chunking.chunk_size_tokens,
            "overlap_tokens": settings.chunking.overlap_tokens,
        },
        "retrieval": {
            "top_k": settings.retrieval.top_k,
            "use_hybrid_search": settings.retrieval.use_hybrid_search,
        },
        "embedding": {
            "model_id": settings.embedding.model_id,
            "dimensions": settings.embedding.dimensions,
        },
        "llm": {
            "model_id": settings.llm.model_id,
            "temperature": settings.llm.temperature,
        },
    }
