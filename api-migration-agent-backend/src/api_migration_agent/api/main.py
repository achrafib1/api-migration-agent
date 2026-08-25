"""FastAPI application factory and process-local production lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import InMemorySaver

from api_migration_agent.api.routes import router
from api_migration_agent.application.planning import build_production_planning_graph
from api_migration_agent.core.config import Settings, get_settings
from api_migration_agent.core.exceptions import ApiMigrationError, MigrationRunNotFoundError
from api_migration_agent.domain.migration_target import MigrationTargetSummary
from api_migration_agent.infrastructure.run_store import MemoryMigrationRunStore
from api_migration_agent.infrastructure.target_registry import StaticMigrationTargetRegistry
from api_migration_agent.services.planning_workflow import PlanningWorkflowService
from api_migration_agent.services.target_registry import TrustedMigrationTarget


def bundled_atlaspay_root() -> Path:
    """Return the repository-owned trusted AtlasPay fixture directory.

    Returns:
        The absolute fixture path derived from the installed source layout.
    """

    return Path(__file__).resolve().parents[4] / "examples" / "atlaspay"


def create_app(
    *,
    planning_service: PlanningWorkflowService | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create the API with injectable service wiring for isolated tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if planning_service is not None:
            app.state.planning_workflow_service = planning_service
        else:
            graph = build_production_planning_graph(
                checkpointer=InMemorySaver(),
                settings=resolved_settings,
            )
            app.state.planning_workflow_service = PlanningWorkflowService(
                graph=graph,
                store=MemoryMigrationRunStore(),
                target_registry=_production_target_registry(),
            )
        yield

    resolved_settings = settings or get_settings()
    app = FastAPI(title="API Migration Agent", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        """Return non-sensitive process health without provider configuration."""

        return {"status": "ok"}

    @app.exception_handler(ApiMigrationError)
    async def handle_domain_error(request: Request, exc: ApiMigrationError) -> JSONResponse:
        """Return only stable error metadata and discard internal context."""

        return JSONResponse(
            status_code=404 if isinstance(exc, MigrationRunNotFoundError) else 400,
            content={"error_code": exc.error_code, "message": exc.public_message},
        )

    return app


def _production_target_registry() -> StaticMigrationTargetRegistry:
    """Build the startup-validated catalog of server-approved local targets."""

    atlaspay_root = bundled_atlaspay_root()
    return StaticMigrationTargetRegistry(
        (
            TrustedMigrationTarget(
                summary=MigrationTargetSummary(
                    id="atlaspay",
                    name="AtlasPay Python client",
                    description="Bundled trusted demonstration migration from API v1 to v2.",
                ),
                root=atlaspay_root,
                old_spec_path=atlaspay_root / "specs" / "atlaspay-v1.json",
                new_spec_path=atlaspay_root / "specs" / "atlaspay-v2.json",
                repository_path=atlaspay_root / "client-repository",
            ),
        )
    )


app = create_app()
