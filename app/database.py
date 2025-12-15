# snap-2-track-backend/app/database.py
from sqlmodel import SQLModel, create_engine, Session
import os
from dotenv import load_dotenv

load_dotenv()

# Build Postgres URL from individual env vars if DATABASE_URL is not set directly
if not os.getenv("DATABASE_URL"):
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "password")
    db_host = os.getenv("DB_HOST", "192.168.2.2")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_DATABASE", "snap2track")
    DATABASE_URL = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

# Echo=False for production noise reduction
engine = create_engine(DATABASE_URL, echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session