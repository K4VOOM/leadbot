from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix":"ix_%(column_0_label)s",
        "uq":"uq_%(table_name)s_%(column_0_name)s",
        "ck":"ck_%(table_name)s_%(constraint_name)s",
        "fk":"fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk":"pk_%(table_name)s"})