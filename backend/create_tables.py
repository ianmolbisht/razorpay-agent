from app.db.base import Base
from app.db.database import engine
import app.models


Base.metadata.create_all(bind=engine)

print("Database tables created successfully")