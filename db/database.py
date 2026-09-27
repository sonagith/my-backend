# db/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database file ka naam gharpilot.db hoga, jo aapke Backend folder me ban jayegi
SQLALCHEMY_DATABASE_URL = "sqlite:///./gharpilot.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()