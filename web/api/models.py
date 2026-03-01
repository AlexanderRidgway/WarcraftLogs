from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_name: Mapped[str] = mapped_column(String(20), nullable=False)
    server: Mapped[str] = mapped_column(String(50), nullable=False)
    region: Mapped[str] = mapped_column(String(10), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rankings: Mapped[list["Ranking"]] = relationship(back_populates="player")
    scores: Mapped[list["Score"]] = relationship(back_populates="player")
    gear_snapshots: Mapped[list["GearSnapshot"]] = relationship(back_populates="player")
    utility_data: Mapped[list["UtilityData"]] = relationship(back_populates="player")
    consumables_data: Mapped[list["ConsumablesData"]] = relationship(back_populates="player")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="player")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    zone_id: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    player_names: Mapped[dict] = mapped_column(JSON, nullable=False)


class Ranking(Base):
    __tablename__ = "rankings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    encounter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    spec: Mapped[str] = mapped_column(String(30), nullable=False)
    rank_percent: Mapped[float] = mapped_column(Float, nullable=False)
    zone_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="rankings")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    spec: Mapped[str] = mapped_column(String(30), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    parse_score: Mapped[float] = mapped_column(Float, nullable=False)
    utility_score: Mapped[float] = mapped_column(Float, nullable=True)
    consumables_score: Mapped[float] = mapped_column(Float, nullable=True)
    fight_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="scores")


class GearSnapshot(Base):
    __tablename__ = "gear_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_level: Mapped[int] = mapped_column(Integer, nullable=False)
    quality: Mapped[int] = mapped_column(Integer, nullable=False)
    permanent_enchant: Mapped[int] = mapped_column(Integer, nullable=True)
    gems: Mapped[dict] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    player: Mapped["Player"] = relationship(back_populates="gear_snapshots")


class UtilityData(Base):
    __tablename__ = "utility_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)

    player: Mapped["Player"] = relationship(back_populates="utility_data")


class ConsumablesData(Base):
    __tablename__ = "consumables_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    report_code: Mapped[str] = mapped_column(String(20), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    player: Mapped["Player"] = relationship(back_populates="consumables_data")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_id: Mapped[int] = mapped_column(Integer, nullable=False)
    zone_label: Mapped[str] = mapped_column(String(50), nullable=False)
    clear_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[int] = mapped_column(Integer, nullable=False)
    met: Mapped[bool] = mapped_column(Boolean, nullable=False)

    player: Mapped["Player"] = relationship(back_populates="attendance_records")

    __table_args__ = (
        UniqueConstraint("player_id", "year", "week_number", "zone_id", name="uq_attendance_player_week_zone"),
    )


class SyncStatus(Base):
    __tablename__ = "sync_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_type: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
