from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.database.base import Base
from app.database.session import engine


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============================================================
# UPLOAD DIRECTORY
# ============================================================

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Existing upload route
app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads",
)

# Static route for files currently being returned by
# the upload API as /static/uploads/...
STATIC_DIR = Path("static")
STATIC_UPLOAD_DIR = STATIC_DIR / "uploads"

STATIC_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


# ============================================================
# CORS
# ============================================================

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "https://localhost:5174",
    "http://192.168.18.83:5173",
    "http://192.168.18.83:5174",
    "https://192.168.18.83:5174",
    "http://localhost:3000",
    "https://realtimechatbot-frontend.vercel.app",
]

# Merge settings origins if available
if getattr(settings, "BACKEND_CORS_ORIGINS", None):
    if isinstance(settings.BACKEND_CORS_ORIGINS, list):
        origins.extend(
            [
                str(origin)
                for origin in settings.BACKEND_CORS_ORIGINS
            ]
        )

    elif isinstance(settings.BACKEND_CORS_ORIGINS, str):
        origins.extend(
            [
                o.strip()
                for o in settings.BACKEND_CORS_ORIGINS.split(",")
                if o.strip()
            ]
        )


# ============================================================
# CORS MIDDLEWARE
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API + WEBSOCKET ROUTERS
# ============================================================

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )


# ============================================================
# HEALTH / ROOT
# ============================================================

@app.get("/", tags=["health"])
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
    }


@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "ok"
    }