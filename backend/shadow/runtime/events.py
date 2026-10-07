"""Append-only outcome ledger."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from shadow.core.models import RuntimeEvent


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[str] = mapped_column(String(128))


class ContractRow(Base):
    __tablename__ = "approved_futures"
    contract_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32))
    payload: Mapped[str] = mapped_column(Text)


class EventLog:
    def __init__(self, url: str = "sqlite://") -> None:
        kwargs: dict[str, object] = {"future": True}
        if url == "sqlite://":
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)  # type: ignore[arg-type]
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self._lock = threading.Lock()

    def append(self, plan_id: str, event_type: str, payload: dict[str, Any], provenance: str) -> RuntimeEvent:
        encoded = json.dumps(payload, sort_keys=True, default=str)
        event = RuntimeEvent(
            event_id=uuid.uuid4().hex,
            plan_id=plan_id,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            event_type=event_type,
            payload=payload,
            payload_hash=hashlib.sha256(encoded.encode()).hexdigest(),
            provenance=provenance,
        )
        with self._lock, self.factory() as session:
            session.add(
                EventRow(
                    event_id=event.event_id,
                    plan_id=event.plan_id,
                    timestamp=event.timestamp,
                    event_type=event.event_type,
                    payload=encoded,
                    payload_hash=event.payload_hash,
                    provenance=event.provenance,
                )
            )
            session.commit()
        return event

    def list_for(self, plan_id: str) -> list[RuntimeEvent]:
        with self._lock, self.factory() as session:
            rows = session.query(EventRow).filter(EventRow.plan_id == plan_id).all()
        return [
            RuntimeEvent(
                event_id=row.event_id,
                plan_id=row.plan_id,
                timestamp=row.timestamp,
                event_type=row.event_type,
                payload=json.loads(row.payload),
                payload_hash=row.payload_hash,
                provenance=row.provenance,
            )
            for row in rows
        ]

    def replay_resources(self, plan_id: str) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for event in self.list_for(plan_id):
            if event.event_type == "ACTION_EXECUTED":
                resource = event.payload.get("resource")
                if resource:
                    state[resource] = event.payload.get("effects")
            if event.event_type == "COMPENSATION_EXECUTED":
                resource = event.payload.get("resource")
                if resource:
                    state[resource] = {"compensated": True}
        return state

    def save_approved(self, contract_id: str, plan_id: str, status: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, default=str)
        with self._lock, self.factory() as session:
            row = session.get(ContractRow, contract_id)
            if row is None:
                session.add(ContractRow(contract_id=contract_id, plan_id=plan_id, status=status, payload=encoded))
            else:
                row.status = status
                row.plan_id = plan_id
                row.payload = encoded
            session.commit()

    def clear_approved(self) -> None:
        with self._lock, self.factory() as session:
            session.query(ContractRow).delete()
            session.commit()

    def load_approved(self, statuses: tuple[str, ...] = ("ACTIVE", "REAFFIRMED")) -> list[dict[str, Any]]:
        with self._lock, self.factory() as session:
            rows = session.query(ContractRow).all()
        found = []
        for row in rows:
            if row.status not in statuses:
                continue
            payload = json.loads(row.payload)
            payload["status"] = row.status
            found.append(payload)
        return found
