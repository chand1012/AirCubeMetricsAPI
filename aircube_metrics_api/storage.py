from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine, select


Aggregate = Literal["hour", "day"]


class AirCubeReading(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recorded_at: datetime = Field(index=True)
    temp_c: float
    humidity: float
    eco2: float
    etvoc: float
    voc_level: float
    timestamp_ms: int


class AirCubeAggregate(SQLModel):
    bucket: str
    temp_c: float
    humidity: float
    eco2: float
    etvoc: float
    voc_level: float
    sample_count: int


class AirCubeStore:
    def __init__(self, database_url: str, retention_days: int = 7):
        engine_kwargs = {}
        if database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        if database_url == "sqlite:///:memory:":
            engine_kwargs["poolclass"] = StaticPool

        self.engine = create_engine(
            database_url,
            **engine_kwargs,
        )
        self.retention_days = retention_days

    def create_schema(self):
        SQLModel.metadata.create_all(self.engine)

    def close(self):
        self.engine.dispose()

    def add_reading(self, reading):
        recorded_at = reading.get("recorded_at") or datetime.now(UTC)
        row = AirCubeReading(
            recorded_at=_normalize_datetime(recorded_at),
            temp_c=reading["temp_c"],
            humidity=reading["humidity"],
            eco2=reading["eco2"],
            etvoc=reading["etvoc"],
            voc_level=reading["voc_level"],
            timestamp_ms=reading["timestamp_ms"],
        )
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def latest(self):
        with Session(self.engine) as session:
            statement = select(AirCubeReading).order_by(AirCubeReading.recorded_at.desc(), AirCubeReading.id.desc())
            return session.exec(statement).first()

    def query_readings(self, start=None, end=None, limit=1000):
        statement = select(AirCubeReading).order_by(AirCubeReading.recorded_at)
        if start is not None:
            statement = statement.where(AirCubeReading.recorded_at >= _normalize_datetime(start))
        if end is not None:
            statement = statement.where(AirCubeReading.recorded_at < _normalize_datetime(end))
        if limit is not None:
            statement = statement.limit(limit)

        with Session(self.engine) as session:
            return list(session.exec(statement).all())

    def query_aggregates(self, start=None, end=None, aggregate: Aggregate = "day"):
        bucket_expression = _bucket_expression(aggregate)
        statement = (
            select(
                bucket_expression.label("bucket"),
                func.avg(AirCubeReading.temp_c).label("temp_c"),
                func.avg(AirCubeReading.humidity).label("humidity"),
                func.avg(AirCubeReading.eco2).label("eco2"),
                func.avg(AirCubeReading.etvoc).label("etvoc"),
                func.avg(AirCubeReading.voc_level).label("voc_level"),
                func.count(AirCubeReading.id).label("sample_count"),
            )
            .group_by(bucket_expression)
            .order_by(bucket_expression)
        )
        if start is not None:
            statement = statement.where(AirCubeReading.recorded_at >= _normalize_datetime(start))
        if end is not None:
            statement = statement.where(AirCubeReading.recorded_at < _normalize_datetime(end))

        with Session(self.engine) as session:
            rows = session.exec(statement).all()
            return [
                AirCubeAggregate(
                    bucket=row.bucket,
                    temp_c=row.temp_c,
                    humidity=row.humidity,
                    eco2=row.eco2,
                    etvoc=row.etvoc,
                    voc_level=row.voc_level,
                    sample_count=row.sample_count,
                )
                for row in rows
            ]

    def cleanup(self, now=None):
        cutoff = _normalize_datetime(now or datetime.now(UTC)) - timedelta(days=self.retention_days)
        with Session(self.engine) as session:
            rows = list(session.exec(select(AirCubeReading).where(AirCubeReading.recorded_at < cutoff)).all())
            for row in rows:
                session.delete(row)
            session.commit()
            return len(rows)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _bucket_expression(aggregate: Aggregate):
    if aggregate == "hour":
        return func.strftime("%Y-%m-%dT%H:00:00Z", AirCubeReading.recorded_at)
    if aggregate == "day":
        return func.strftime("%Y-%m-%d", AirCubeReading.recorded_at)
    raise ValueError(f"Unsupported aggregate: {aggregate}")
