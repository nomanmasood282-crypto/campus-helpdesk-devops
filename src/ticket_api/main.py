from __future__ import annotations

import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class TicketStatusUpdate(BaseModel):
    status: TicketStatus


class Ticket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TicketStatus
    created_at: datetime


def _connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved')),
                created_at TEXT NOT NULL
            )
            """
        )


def _ticket_from_row(row: sqlite3.Row) -> Ticket:
    return Ticket(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def create_app(database_path: str | Path = "data/tickets.db") -> FastAPI:
    database = Path(database_path)
    registry = CollectorRegistry()
    request_count = Counter(
        "http_requests_total",
        "Total HTTP requests served by the ticket API.",
        ("method", "path", "status_code"),
        registry=registry,
    )
    request_duration = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds.",
        ("method", "path"),
        registry=registry,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _initialize_database(database)
        yield

    app = FastAPI(
        title="Campus Helpdesk Ticket API",
        description="A small ticket service for demonstrating a GitOps delivery workflow.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def record_request_metrics(request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start_time
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        request_count.labels(request.method, path, str(response.status_code)).inc()
        request_duration.labels(request.method, path).observe(duration)
        return response

    @app.get("/health/live", tags=["health"])
    def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    def readiness() -> dict[str, str]:
        with _connect(database) as connection:
            connection.execute("SELECT 1")
        return {"status": "ready"}

    @app.post("/tickets", response_model=Ticket, status_code=201, tags=["tickets"])
    def create_ticket(ticket: TicketCreate) -> Ticket:
        created_at = datetime.now(timezone.utc)
        with _connect(database) as connection:
            cursor = connection.execute(
                """
                INSERT INTO tickets (title, description, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (ticket.title, ticket.description, TicketStatus.OPEN.value, created_at.isoformat()),
            )
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return _ticket_from_row(row)

    @app.get("/tickets", response_model=list[Ticket], tags=["tickets"])
    def list_tickets(
        status: Annotated[TicketStatus | None, Query()] = None,
    ) -> list[Ticket]:
        with _connect(database) as connection:
            if status is None:
                rows = connection.execute("SELECT * FROM tickets ORDER BY id").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM tickets WHERE status = ? ORDER BY id", (status.value,)
                ).fetchall()
        return [_ticket_from_row(row) for row in rows]

    @app.get("/tickets/{ticket_id}", response_model=Ticket, tags=["tickets"])
    def get_ticket(ticket_id: int) -> Ticket:
        with _connect(database) as connection:
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return _ticket_from_row(row)

    @app.patch("/tickets/{ticket_id}", response_model=Ticket, tags=["tickets"])
    def update_ticket(ticket_id: int, update: TicketStatusUpdate) -> Ticket:
        with _connect(database) as connection:
            cursor = connection.execute(
                "UPDATE tickets SET status = ? WHERE id = ?",
                (update.status.value, ticket_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Ticket not found")
            row = connection.execute(
                "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        return _ticket_from_row(row)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
