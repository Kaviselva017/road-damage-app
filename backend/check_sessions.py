import os
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
os.environ["MAX_CONCURRENT_SESSIONS"] = "5"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.models import User
from app.models.refresh_token import RefreshToken
from app.services.token_service import issue_token_pair, MAX_SESSIONS

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

db = SessionLocal()
user = User(google_sub="sub1", email="test@test.com", name="Test", phone_number="+123")
db.add(user)
db.commit()

for i in range(MAX_SESSIONS + 1):
    pair = issue_token_pair(user, db)
    print(f"Issued {i}: active count =", db.query(RefreshToken).filter_by(revoked=False).count())

active = db.query(RefreshToken).filter_by(revoked=False).count()
print("Final active:", active)
