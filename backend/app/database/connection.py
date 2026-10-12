from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.settings import settings

# Створюємо URL для підключення до PostgreSQL
DATABASE_URL = settings.database_url

# Створюємо двигун SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    echo=settings.database_echo, 
    pool_pre_ping=True,  # Перевірка з'єднання перед використанням
    pool_recycle=300,  # Перезапуск з'єднань кожні 5 хвилин
    connect_args={
        "client_encoding": "utf8",
        "options": "-c timezone=UTC -c client_encoding=utf8"
    }
)

# Створюємо фабрику сесій
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовий клас для моделей
Base = declarative_base()


def get_db():
    """Dependency для отримання сесії бази даних"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
