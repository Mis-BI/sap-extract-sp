"""FastAPI entrypoint for SAP automation."""
from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request

from app.api.routes.sap_automation import router as sap_router
from app.core.logging_config import configure_logging, reset_request_id, set_request_id
from app.core.settings import get_settings


settings = get_settings()
configure_logging(settings)

app = FastAPI(title="SAP Automation API", version="1.0.0")
app.include_router(sap_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid4())
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
    finally:
        reset_request_id(token)

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """Simple health endpoint."""
    return {"status": "ok"}
