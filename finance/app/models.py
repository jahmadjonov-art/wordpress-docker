from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Text, Date, DateTime, Float, Boolean, ForeignKey, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class IncomeEntry(Base):
    __tablename__ = "income_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    week_ending: Mapped[date] = mapped_column(Date, index=True)
    gross_cents: Mapped[int] = mapped_column(Integer)
    net_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    miles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="W-2 company driver")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExpenseEntry(Base):
    __tablename__ = "expense_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), index=True)  # "2026-04"
    category: Mapped[str] = mapped_column(String(64))
    amount_cents: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SavingsGoal(Base):
    __tablename__ = "savings_goal"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_cents: Mapped[int] = mapped_column(Integer)
    buckets_json: Mapped[str] = mapped_column(Text)
    weekly_save_cents: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SavingsSnapshot(Base):
    __tablename__ = "savings_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    as_of: Mapped[date] = mapped_column(Date, index=True)
    balance_cents: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16), default="derived")


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_url: Mapped[str] = mapped_column(String(1024), unique=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(512))
    asking_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    make: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    engine: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transmission: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mileage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_state: Mapped[str | None] = mapped_column(String(4), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    vin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # trailer-specific
    trailer_length_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trailer_door: Mapped[str | None] = mapped_column(String(16), nullable=True)
    trailer_walls: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trailer_suspension: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # audit
    fetch_method: Mapped[str] = mapped_column(String(16), default="manual")
    raw_html_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_starred: Mapped[bool] = mapped_column(Boolean, default=False)

    scores: Mapped[list["ListingScore"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="desc(ListingScore.scored_at)",
    )


Index("ix_listings_first_seen", Listing.first_seen.desc())


class ListingScore(Base):
    __tablename__ = "listing_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    comp_count: Mapped[int] = mapped_column(Integer, default=0)
    median_comp_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    breakdown_json: Mapped[str] = mapped_column(Text, default="{}")

    listing: Mapped["Listing"] = relationship(back_populates="scores")


class MarketStat(Base):
    __tablename__ = "market_stats"
    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(32))
    make: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    year_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mileage_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer)
    median_cents: Mapped[int] = mapped_column(Integer)
    p25_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p75_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    listings_new: Mapped[int] = mapped_column(Integer, default=0)
    listings_updated: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ok")
