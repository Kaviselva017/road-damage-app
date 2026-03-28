from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import FieldOfficer
from app.schemas.schemas import OfficerDirectoryOut
from app.services.auth_service import get_current_officer

router = APIRouter()

@router.get("/", response_model=List[OfficerDirectoryOut])
def list_officers(
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer),
):
    return db.query(FieldOfficer).filter(FieldOfficer.is_active == 1).all()
