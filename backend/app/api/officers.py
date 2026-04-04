"""Officer directory — authenticated officers can list active colleagues."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import FieldOfficer
from app.schemas.schemas import OfficerDirectoryOut
from app.dependencies import get_current_officer

router = APIRouter(prefix="/officers", tags=["officers"])


@router.get("/", response_model=List[OfficerDirectoryOut])
def list_officers(
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer),
):
    return db.query(FieldOfficer).filter(FieldOfficer.is_active == True).all()
