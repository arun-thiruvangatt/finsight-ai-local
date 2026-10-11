from sqlalchemy import create_engine

from app.core.config import get_settings

engine = create_engine(get_settings().DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
