"""FastAPI UI service for Problemata control-plane workflows."""

from __future__ import annotations

import inspect
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import get_current_tenant
from .problemata_control import (
    AsyncProblemataControlService,
    create_default_postgres_problemata_service,
    InMemoryProblemataRepository,
    ProblemataBlueprint,
    ProblemataControlService,
    ProblemataDiagnosticsResult,
    PostgresProblemataRepository,
    ProblemataRecord,
)
from .problemata_validation import ProblemataValidationResult


class ProblemataSpecPayload(BaseModel):
    """Request payload for operations that take a raw Problemata spec."""

    spec: dict[str, Any]


class ProblemataRegisterPayload(ProblemataSpecPayload):
    """Request payload for persisting a raw Problemata spec."""

    source: str = Field(default="ui.raw")


def _get_control_service(request: Request) -> Any:
    return request.app.state.problemata_control_service


def _resolve_ui_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "tools" / "problemata_control_ui"


async def _resolve_maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def create_app(service: Any | None = None) -> FastAPI:
    """Create a Problemata control UI app instance."""
    ui_dir = _resolve_ui_dir()
    index_file = ui_dir / "index.html"
    assets_dir = ui_dir / "assets"

    managed_repository: PostgresProblemataRepository | None = None
    resolved_service = service
    if resolved_service is None:
        backend = os.environ.get("PROBLEMATA_STORAGE_BACKEND", "postgres").strip().lower()
        if backend == "memory":
            resolved_service = ProblemataControlService(repository=InMemoryProblemataRepository())
        else:
            resolved_service, managed_repository = create_default_postgres_problemata_service()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if managed_repository is not None:
            await managed_repository.startup()
        yield
        if managed_repository is not None:
            await managed_repository.shutdown()

    app = FastAPI(
        title="LegiVellum Problemata Control UI",
        version="0.1.0",
        description="Control plane and GUI for Problemata creation and validation.",
        lifespan=lifespan,
    )
    app.state.problemata_control_service = resolved_service
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/api/health")
    async def health(
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> dict[str, Any]:
        records = await _resolve_maybe_await(control_service.list())
        return {
            "status": "ok",
            "service": "problemata-control-ui",
            "storage_backend": "postgres" if isinstance(control_service, AsyncProblemataControlService) else "memory",
            "total_problemata": len(records),
        }

    @app.post("/api/problemata/preview")
    async def preview_problemata(
        blueprint: ProblemataBlueprint,
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> dict[str, Any]:
        return await _resolve_maybe_await(control_service.preview_from_blueprint(blueprint))

    @app.post("/api/problemata/validate", response_model=ProblemataValidationResult)
    async def validate_problemata(
        payload: ProblemataSpecPayload,
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> ProblemataValidationResult:
        return await _resolve_maybe_await(control_service.validate_spec(payload.spec))

    @app.post("/api/problemata/diagnostics", response_model=ProblemataDiagnosticsResult)
    async def diagnose_problemata(
        payload: ProblemataSpecPayload,
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> ProblemataDiagnosticsResult:
        return await _resolve_maybe_await(control_service.diagnose_spec(payload.spec))

    @app.post("/api/problemata", response_model=ProblemataRecord, status_code=status.HTTP_201_CREATED)
    async def create_problemata_from_spec(
        payload: ProblemataRegisterPayload,
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> ProblemataRecord:
        return await _resolve_maybe_await(control_service.register_spec(payload.spec, source=payload.source))

    @app.put("/api/problemata/{problemata_id}", response_model=ProblemataRecord)
    async def update_problemata_spec(
        problemata_id: str,
        payload: ProblemataRegisterPayload,
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> ProblemataRecord:
        try:
            return await _resolve_maybe_await(
                control_service.update_spec(problemata_id, payload.spec, source=payload.source)
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/api/problemata/from-blueprint", response_model=ProblemataRecord, status_code=status.HTTP_201_CREATED)
    async def create_problemata_from_blueprint(
        blueprint: ProblemataBlueprint,
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> ProblemataRecord:
        return await _resolve_maybe_await(control_service.create_from_blueprint(blueprint))

    @app.get("/api/problemata", response_model=list[ProblemataRecord])
    async def list_problemata(
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> list[ProblemataRecord]:
        return await _resolve_maybe_await(control_service.list())

    @app.get("/api/problemata/{problemata_id}", response_model=ProblemataRecord)
    async def get_problemata(
        problemata_id: str,
        _tenant_id: str = Depends(get_current_tenant),
        control_service: Any = Depends(_get_control_service),
    ) -> ProblemataRecord:
        record = await _resolve_maybe_await(control_service.get(problemata_id))
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problemata not found: {problemata_id}",
            )
        return record

    return app


app = create_app()
