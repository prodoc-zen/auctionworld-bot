from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utc_now():
    return datetime.utcnow()


def format_earnings(bgls: int, dls: int, wls: int) -> str:
    """Format BGLs/DLs/WLs into a readable string, skipping zeros."""
    parts = []
    if bgls: parts.append(f"{bgls} BGLs")
    if dls:  parts.append(f"{dls} DLs")
    if wls:  parts.append(f"{wls} WLs")
    return " ".join(parts) if parts else "0 WLs"


def to_wls(bgls: int, dls: int, wls: int) -> int:
    """Convert all earnings to WLs for math."""
    return (bgls * 10000) + (dls * 100) + wls


def from_wls(total_wls: int) -> tuple[int, int, int]:
    """Convert total WLs back to BGLs, DLs, WLs."""
    bgls, remainder = divmod(total_wls, 10000)
    dls,  wls       = divmod(remainder, 100)
    return bgls, dls, wls


class User(Base):
    __tablename__ = "users"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    jennies: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    admin_user: Mapped["AdminUser"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AdminUser(Base):
    __tablename__ = "admin_users"

    discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship(back_populates="admin_user")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("discord_id", "reason", name="uq_transactions_discord_reason"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    user: Mapped[User] = relationship(back_populates="transactions")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), nullable=False, index=True)
    time_in_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    time_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    bgls: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    dls: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    wls: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship(back_populates="attendance_records")


class HostingQueueEntry(Base):
    __tablename__ = "hosting_queue_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    queue_name: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting", index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version: Mapped[str] = mapped_column(String(255), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class AdminProfile(Base):
    __tablename__ = "admin_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    gt_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    priority_tickets: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class Strike(Base):
    __tablename__ = "strikes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    issued_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    screenshot_url: Mapped[str] = mapped_column(String(500), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    screenshot_url: Mapped[str] = mapped_column(String(500), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class Blacklist(Base):
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    removed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class GachaCard(Base):
    __tablename__ = "gacha_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    character_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rarity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    level: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class GachaShowcase(Base):
    __tablename__ = "gacha_showcase"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    slot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    card_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("gacha_cards.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class MegaphoneSubmission(Base):
    __tablename__ = "megaphone_submissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    screenshot_url: Mapped[str] = mapped_column(String(500), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
