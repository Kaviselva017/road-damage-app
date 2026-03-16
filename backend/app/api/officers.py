from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import FieldOfficer
from app.schemas.schemas import OfficerOut

router = APIRouter()

@router.get("/", response_model=List[OfficerOut])
def list_officers(db: Session = Depends(get_db)):
    return db.query(FieldOfficer).filter(FieldOfficer.is_active == 1).all()
