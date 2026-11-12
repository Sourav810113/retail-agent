"""App factory (AD-2). Run: uvicorn src.retail_agent.main:app --port 8000"""

from __future__ import annotations

from fastapi import FastAPI

from .api import health, orders
from .api.errors import register_error_handlers
from .core.clock import Clock, SystemClock
from .core.db import UnitOfWork, connect
from .core.settings import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from .repositories.schema import apply_schema
from .repositories.seed import seed as seed_data


def create_app(clock: Clock | None = None, seed: bool = True) -> FastAPI:
    clock = clock or SystemClock()
    conn = connect()
    apply_schema(conn)
    uow = UnitOfWork(conn)
    if seed:
        with uow.transaction():
            seed_data(uow, clock)

    app = FastAPI(title=APP_TITLE, version=APP_VERSION, description=APP_DESCRIPTION)
    app.state.clock = clock
    app.state.db = conn
    app.state.uow = uow
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(orders.router)
    return app


app = create_app()
