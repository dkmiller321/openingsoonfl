"""Database tables (PRD: Data model). De-duplication lives in the unique constraints."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    trigger: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10))
    rows_fetched: Mapped[int] = mapped_column(Integer, default=0)
    rows_new: Mapped[int] = mapped_column(Integer, default=0)
    leads_created: Mapped[int] = mapped_column(Integer, default=0)
    leads_updated: Mapped[int] = mapped_column(Integer, default=0)
    problem: Mapped[str | None] = mapped_column(String(30))
    error: Mapped[str | None] = mapped_column(Text)


class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = (UniqueConstraint("source", "content_hash", name="uq_raw_source_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    file: Mapped[str] = mapped_column(String(60))
    source_record_id: Mapped[str | None] = mapped_column(String(60))
    content_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[int] = mapped_column(ForeignKey("source_runs.id"))


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_key: Mapped[str] = mapped_column(String(300), unique=True)
    licence_number: Mapped[str | None] = mapped_column(String(20), index=True)
    business_name: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(100))
    zip: Mapped[str] = mapped_column(String(10))
    county: Mapped[str] = mapped_column(String(40), index=True)
    lead_type: Mapped[str] = mapped_column(String(20))
    stage: Mapped[str] = mapped_column(String(20))
    licensee: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    first_seen: Mapped[date] = mapped_column(Date, index=True)
    licensed_on: Mapped[date | None] = mapped_column(Date)
    days_ahead: Mapped[int | None] = mapped_column(Integer)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    note: Mapped[str | None] = mapped_column(Text)


class LeadKey(Base):
    """Every identity a lead is known by: `K:<name|address|zip>` and `LIC:<digits>`."""

    __tablename__ = "lead_keys"

    key: Mapped[str] = mapped_column(String(320), primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)


class LeadEvent(Base):
    __tablename__ = "lead_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    raw_record_id: Mapped[int] = mapped_column(ForeignKey("raw_records.id"), unique=True)
    source: Mapped[str] = mapped_column(String(40))
    stage: Mapped[str] = mapped_column(String(20))
    event_date: Mapped[date] = mapped_column(Date)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    position: Mapped[int] = mapped_column(Integer)


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    emails: Mapped[list[str]] = mapped_column(ARRAY(String(200)))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    counties: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
    cadence: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Digest(Base):
    __tablename__ = "digests"
    __table_args__ = (
        Index(
            "uq_digest_vendor_period",
            "vendor_id",
            "period_key",
            unique=True,
            postgresql_where=text("kind = 'scheduled'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    kind: Mapped[str] = mapped_column(String(10))
    period_key: Mapped[str | None] = mapped_column(String(20))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lead_count: Mapped[int] = mapped_column(Integer)
    email_id: Mapped[str | None] = mapped_column(String(100))


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("vendor_id", "lead_id", name="uq_delivery_vendor_lead"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    digest_id: Mapped[int] = mapped_column(ForeignKey("digests.id"))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxEmail(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    to: Mapped[list[str]] = mapped_column(ARRAY(String(200)))
    subject: Mapped[str] = mapped_column(String(300))
    html: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HealthAlert(Base):
    """One 'stale' alert per source per stale episode (keyed by its last good run)."""

    __tablename__ = "health_alerts"
    __table_args__ = (UniqueConstraint("source", "reason", "episode", name="uq_health_episode"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(30))
    episode: Mapped[str] = mapped_column(String(40))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


ALL_TABLES = [t.name for t in Base.metadata.sorted_tables]
