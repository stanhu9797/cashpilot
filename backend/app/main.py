"""CashPilot API. In production this one server also serves the built React app."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_db
from .routers import ask, auth, dashboard, forecast, receipts, transactions

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cashpilot")
settings = get_settings()



IS_PROD = settings.app_env == "production"


def startup() -> None:
    """Checks and setup that run once per process (once per cold start on Lambda)."""
    if IS_PROD and (settings.jwt_secret == "change-me-in-production" or len(settings.jwt_secret) < 32):
        # Refuse to start: anyone could forge sign-in tokens with the default secret
        raise RuntimeError("Set JWT_SECRET to a random value of at least 32 characters before running in production.")
    if IS_PROD and not settings.database_url and not settings.demo_mode:
        raise RuntimeError(
            "Set DATABASE_URL in production, or DEMO_MODE=true for a demo that resets on every deploy."
        )
    init_db()
    if settings.demo_mode:
        from .seed import main as seed_demo

        seed_demo()
        log.warning("DEMO_MODE is on: data lives in the container and resets on every restart or deploy.")
    log.info("AI provider: %s (configured: %s)", settings.ai_provider, settings.ai_configured)


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup()
    yield


app = FastAPI(
    title="CashPilot API",
    version="1.1.0",
    lifespan=lifespan,
    # The interactive API docs map every endpoint; useful locally, not something to publish
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None,
    openapi_url=None if IS_PROD else "/openapi.json",
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if IS_PROD:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")  # financial data shouldn't sit in caches
    return response

_any_origin = settings.cors_origin_list == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=not _any_origin,  # sign-in uses a bearer token, so cookies are never needed
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # Turn Pydantic's technical errors into one readable message per field
    messages = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p not in ("body", "query"))
        msg = err["msg"].removeprefix("Value error, ")
        messages.append(f"{field}: {msg}" if field else msg)
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Try again."})


@app.get("/health")
def health():
    return {"status": "ok", "ai_configured": settings.ai_configured}


for r in (auth.router, transactions.router, receipts.router, ask.router, forecast.router, dashboard.router):
    app.include_router(r)

# Serve the built frontend (frontend/dist) when it exists — this is how the Docker image works.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = DIST / path
        if path and file.is_file() and DIST in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(DIST / "index.html")
