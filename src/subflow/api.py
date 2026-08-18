from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from subflow.config import SubFlowSettings
from subflow.runtime import CoreRuntime
from subflow.security import (
    require_bounded_content_length,
    security_headers_middleware,
    token_dependency,
)


class HealthResponse(BaseModel):
    status: str
    service: str


class QueuedResponse(BaseModel):
    queued: bool
    message: str


class PlexMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    rating_key: str = Field(alias="ratingKey", pattern=r"^\d+$")


class PlexWebhook(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    event: str
    metadata: PlexMetadata = Field(alias="Metadata")


def create_core_app(settings: SubFlowSettings, runtime: CoreRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        runtime.start()
        try:
            yield
        finally:
            runtime.stop()

    docs_url = "/docs" if settings.api_docs_enabled else None
    app = FastAPI(
        title="SubFlow API",
        version="0.1.0b1",
        debug=False,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.middleware("http")(security_headers_middleware)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="subflow-core")

    require_token = token_dependency(settings.api_token.get_secret_value())
    protected = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])

    @protected.post("/scan", response_model=QueuedResponse)
    async def scan() -> QueuedResponse:
        count = await run_in_threadpool(runtime.scan_now)
        return QueuedResponse(queued=count > 0, message=f"queued {count} item(s)")

    @protected.post("/webhooks/plex", response_model=QueuedResponse)
    async def plex_webhook(request: Request) -> QueuedResponse:
        if not settings.webhook_enabled:
            raise HTTPException(status_code=404, detail="webhook is disabled")
        require_bounded_content_length(request, settings.max_webhook_bytes)
        content_type = request.headers.get("content-type", "").lower()
        try:
            payload: dict[str, Any]
            if content_type.startswith("application/json"):
                payload = json.loads((await request.body()).decode("utf-8"))
            elif "multipart/form-data" in content_type:
                form = await request.form(
                    max_files=1,
                    max_fields=4,
                    max_part_size=settings.max_webhook_bytes,
                )
                raw = form.get("payload")
                if not isinstance(raw, str):
                    raise ValueError("multipart request does not contain a payload field")
                payload = json.loads(raw)
            else:
                raise HTTPException(status_code=415, detail="unsupported content type")
            webhook = PlexWebhook.model_validate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid Plex webhook payload") from exc

        if webhook.event != "library.new":
            return QueuedResponse(queued=False, message="event ignored")
        queued = await run_in_threadpool(runtime.submit_rating_key, webhook.metadata.rating_key)
        return QueuedResponse(queued=queued, message="item queued" if queued else "item not found")

    app.include_router(protected)
    return app
