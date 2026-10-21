from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiMessage(Exception):
    def __init__(self, status_code: int, message: str, code: str = "error") -> None:
        self.status_code = status_code
        self.message = message
        self.code = code


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiMessage)
    async def handle_message(_: Request, exc: ApiMessage) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.message, "code": exc.code}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "An unexpected server error occurred.", "code": "internal_error"}},
        )
