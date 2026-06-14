from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Text, Date, DateTime, Float, Boolean, ForeignKey, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Load(Base):
    __tablename__ = "loads"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    # lane
    origin_city: Mapped[str] = mapped_column(String(64))
    origin_state: Mapped[str] = mapped_column(String(4), index=True)
    dest_city: Mapped[str] = mapped_column(String(64))
    dest_state: Mapped[str] = mapped_column(String(4), index=True)
    origin_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    dest_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    dest_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    # equipment / freight
    equipment: Mapped[str] = mapped_column(String(16), default="van", index=True)
    weight_lbs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commodity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pickup_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # mileage (filled by routing)
    loaded_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadhead_miles: Mapped[float] = mapped_column(Float, default=0.0)
    miles_source: Mapped[str] = mapped_column(String(16), default="none")  # ors|osrm|haversine|manual
    # money
    rate_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_per_mile_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # broker
    broker_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    broker_mc: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # accessorials / cash terms (fold into true net profit)
    lumper_fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(16), nullable=True)  # quickpay|net15|net30|...
    # freeform
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # negotiation letter (cached after generation)
    letter_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    letter_generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # audit
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    user_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scores: Mapped[list["LoadScore"]] = relationship(
        back_populates="load",
        cascade="all, delete-orphan",
        order_by="desc(LoadScore.scored_at)",
    )


Index("ix_loads_created_at", Load.created_at.desc())


class LoadScore(Base):
    __tablename__ = "load_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    load_id: Mapped[int] = mapped_column(ForeignKey("loads.id", ondelete="CASCADE"), index=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    lane_comp_count: Mapped[int] = mapped_column(Integer, default=0)
    median_rpm_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    est_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    est_profit_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suggested_target_rate_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # true-net + hours economics (display)
    net_revenue_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadhead_adj_rpm_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profit_per_hour_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    breakdown_json: Mapped[str] = mapped_column(Text, default="[]")

    load: Mapped["Load"] = relationship(back_populates="scores")


class LaneStat(Base):
    __tablename__ = "lane_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    lane_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    equipment: Mapped[str] = mapped_column(String(16))
    origin_region: Mapped[str] = mapped_column(String(32))
    dest_region: Mapped[str] = mapped_column(String(32))
    sample_count: Mapped[int] = mapped_column(Integer)
    median_rpm_cents: Mapped[int] = mapped_column(Integer)
    p25_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p75_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Broker(Base):
    __tablename__ = "brokers"
    id: Mapped[int] = mapped_column(primary_key=True)
    mc_number: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    dba_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    authority_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    allowed_to_operate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    safety_rating: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # reliability that learns from logged outcomes (Elo-style, seeded at 1500)
    reliability_elo: Mapped[int] = mapped_column(Integer, default=1500)
    outcomes_count: Mapped[int] = mapped_column(Integer, default=0)
    # rolling average of broker margin % the user has personally uncovered (49 CFR 371.3)
    avg_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class FuelPrice(Base):
    __tablename__ = "fuel_prices"
    id: Mapped[int] = mapped_column(primary_key=True)
    region: Mapped[str] = mapped_column(String(32), default="US", index=True)
    diesel_cents_per_gal: Mapped[int] = mapped_column(Integer)
    period: Mapped[str | None] = mapped_column(String(16), nullable=True)  # e.g. "2026-06-08"
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Settings(Base):
    """Single-row (id=1) economics configuration."""
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    mpg: Mapped[float] = mapped_column(Float)
    fixed_monthly_cents: Mapped[int] = mapped_column(Integer)
    avg_monthly_miles: Mapped[int] = mapped_column(Integer)
    maint_cpm_cents: Mapped[int] = mapped_column(Integer)
    target_margin_pct: Mapped[int] = mapped_column(Integer)
    # true-net + hours-of-service economics
    factoring_pct: Mapped[float] = mapped_column(Float, default=3.0)
    avg_speed_mph: Mapped[float] = mapped_column(Float, default=50.0)
    detention_free_hours: Mapped[float] = mapped_column(Float, default=2.0)
    detention_rate_cents: Mapped[int] = mapped_column(Integer, default=7500)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LoadOutcome(Base):
    """A logged result for a completed load — drives broker reliability Elo."""
    __tablename__ = "load_outcomes"
    id: Mapped[int] = mapped_column(primary_key=True)
    load_id: Mapped[int | None] = mapped_column(ForeignKey("loads.id", ondelete="SET NULL"), nullable=True)
    broker_mc: Mapped[str | None] = mapped_column(String(16), index=True, nullable=True)
    paid_timing: Mapped[str] = mapped_column(String(16))   # on_time|late|short|unpaid
    detention_honored: Mapped[str | None] = mapped_column(String(8), nullable=True)  # yes|no|na
    rate_accurate: Mapped[str | None] = mapped_column(String(8), nullable=True)      # yes|no|na
    tonu: Mapped[bool] = mapped_column(Boolean, default=False)
    margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # broker margin uncovered via 371.3
    elo_delta: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")
