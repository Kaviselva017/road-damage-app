from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_officer
from app.models.models import FieldOfficer
from app.schemas.schemas import OfficerDirectoryOut

"""Officer directory — authenticated officers can list active colleagues."""


router = APIRouter(prefix="/officers", tags=["officers"])


@router.get("/", response_model=list[OfficerDirectoryOut])
def list_officers(
    db: Session = Depends(get_db),
    current_officer: FieldOfficer = Depends(get_current_officer),
):
    return db.execute(select(FieldOfficer).filter(FieldOfficer.is_active.is_(True))).scalars().all()
