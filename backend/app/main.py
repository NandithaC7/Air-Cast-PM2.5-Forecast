from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import get_settings
from backend.app.errors import install_error_handlers
from backend.app.routers import compat, data, health, models, predict

settings = get_settings()

app = FastAPI(
    title="AirCast India API",
    version="1.0.0",
    description="Serves trained next-day PM2.5 hazard models and evaluation artifacts.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

app.include_router(health.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(predict.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(compat.router, prefix="/api/v1")

app.include_router(health.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(compat.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"message": "Request validation failed.", "code": "validation_error", "details": exc.errors()}},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "aircast-india", "docs": "/docs", "health": "/api/v1/health"}
