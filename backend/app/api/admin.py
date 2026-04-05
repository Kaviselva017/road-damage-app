"""
RoadWatch Admin API — field names match EXACTLY what admin.html reads.

Verified from admin.html source:
  loadStats()    → stats.total, .pending, .in_progress, .completed,
                   .high, .medium, .low, .total_officers, .total_citizens,
                   .resolution_rate, .recent_7days
  loadOfficers() → o.total_complaints, .completed, .pending, .resolution_rate,
                   .performance, .zone, .is_active, .name, .email, .phone
  loadCitizens() → c.total_reports, .completed, .fixed, .high_severity,
                   .points, .is_active
  loadComplaints()→ c.complaint_id, .damage_type, .severity, .status,
                    .citizen_name, .citizen_phone, .officer_name, .address,
                    .created_at, .image_url
  chart/daily    → [{date, count}]
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from fpdf import FPDF
import io
import os

from app.database import get_db
from app.models.models import User, FieldOfficer, Complaint, LoginLog
from app.dependencies import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


class OfficerCreate(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    zone: Optional[str] = None

class OfficerEdit(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    zone: Optional[str] = None
    password: Optional[str] = None


class ReassignPayload(BaseModel):
    officer_id: int

class CitizenEdit(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    points: Optional[int] = None
    password: Optional[str] = None


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    from sqlalchemy import func
    _cnt = lambda *filters: db.query(func.count(Complaint.id)).filter(*filters).scalar() or 0
    total    = db.query(func.count(Complaint.id)).scalar() or 0
    pending  = _cnt(Complaint.status == "pending")
    assigned = _cnt(Complaint.status == "assigned")
    in_prog  = _cnt(Complaint.status == "in_progress")
    done     = _cnt(Complaint.status == "completed")
    high     = _cnt(Complaint.severity == "high")
    medium   = _cnt(Complaint.severity == "medium")
    low      = _cnt(Complaint.severity == "low")
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent   = _cnt(Complaint.created_at >= week_ago)
    rate     = round(done / total * 100, 1) if total else 0

    return {
        "total":           total,
        "pending":         pending + assigned,
        "in_progress":     in_prog,
        "completed":       done,
        "high":            high,
        "medium":          medium,
        "low":             low,
        "total_officers":  db.query(func.count(FieldOfficer.id)).filter(FieldOfficer.is_admin == False).scalar() or 0,
        "total_citizens":  db.query(func.count(User.id)).scalar() or 0,
        "resolution_rate": rate,
        "recent_7days":    recent,
        "total_complaints": total,
    }


# ── Complaints ────────────────────────────────────────────────────────────────

@router.get("/complaints")
def list_complaints(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    rows = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    result = []
    for c in rows:
        user    = db.query(User).filter(User.id == c.user_id).first()
        officer = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first() if c.officer_id else None
        result.append({
            "id":              c.id,
            "complaint_id":    c.complaint_id or f"RD-{c.id:06d}",
            "description":     c.description or "",
            "address":         c.address or "",
            "latitude":        c.latitude,
            "longitude":       c.longitude,
            "area_type":       c.area_type or "",
            "damage_type":     c.damage_type or "pothole",
            "severity":        c.severity or "medium",
            "status":          c.status or "pending",
            "ai_confidence":   c.ai_confidence or 0,
            "priority_score":  c.priority_score or 0,
            "image_url":       c.image_url or "",
            "after_image_url": c.after_image_url or "",
            "officer_notes":   c.officer_notes or "",
            "allocated_fund":  c.allocated_fund or 0,
            "is_duplicate":    c.is_duplicate or False,
            "report_count":    c.report_count or 1,
            "created_at":      c.created_at.isoformat() if c.created_at else "",
            "resolved_at":     c.resolved_at.isoformat() if c.resolved_at else None,
            # exact names admin.html renders:
            "citizen_name":    user.name if user else "Unknown",
            "citizen_phone":   user.phone if user else "",
            "citizen_id":      c.user_id,
            "officer_name":    officer.name if officer else "Unassigned",
            "officer_id":      c.officer_id,
        })
    return result


@router.patch("/complaints/{complaint_id}/reassign")
def reassign_complaint(
    complaint_id: str,
    payload: ReassignPayload,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint and complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    officer = db.query(FieldOfficer).filter(FieldOfficer.id == payload.officer_id).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    complaint.officer_id = payload.officer_id
    complaint.status = "assigned"
    db.commit()
    return {"message": "Reassigned", "officer_name": officer.name}


# ── Officers ──────────────────────────────────────────────────────────────────

@router.get("/officers")
def list_officers(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    officers = db.query(FieldOfficer).filter(FieldOfficer.is_admin == False).all()
    result = []
    for o in officers:
        c_all  = db.query(Complaint).filter(Complaint.officer_id == o.id).all()
        total  = len(c_all)
        done   = sum(1 for c in c_all if c.status == "completed")
        pend   = sum(1 for c in c_all if c.status in ("pending", "assigned"))
        rate   = round(done / total * 100, 1) if total else 0
        result.append({
            "id":               o.id,
            "name":             o.name,
            "email":            o.email,
            "phone":            o.phone or "",
            "zone":             o.zone or "",
            "is_active":        o.is_active,
            "last_login":       o.last_login.isoformat() if o.last_login else None,
            "created_at":       o.created_at.isoformat() if o.created_at else "",
            # exact names admin.html uses:
            "total_complaints": total,
            "completed":        done,
            "pending":          pend,
            "resolution_rate":  rate,
            "performance":      rate,
        })
    return result


@router.post("/officers")
def create_officer(
    payload: OfficerCreate,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
    if db.query(FieldOfficer).filter(FieldOfficer.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = pwd_ctx.hash(payload.password)
    new_officer = FieldOfficer(
        name=payload.name.strip(),
        email=email,
        phone=payload.phone,
        zone=payload.zone,
        hashed_password=hashed_password,
        is_admin=False,
    )
    db.add(new_officer)
    db.commit()
    return {"message": "Officer created successfully"}


@router.patch("/officers/{officer_id}")
def edit_officer(
    officer_id: int,
    payload: OfficerEdit,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    if payload.name     is not None: o.name             = payload.name
    if payload.phone    is not None: o.phone            = payload.phone
    if payload.zone     is not None: o.zone             = payload.zone
    if payload.password is not None: o.hashed_password  = pwd_ctx.hash(payload.password)
    db.commit()
    return {"message": "Officer updated"}


@router.delete("/officers/{officer_id}")
def delete_officer(
    officer_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    if o.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin")
    db.delete(o)
    db.commit()
    return {"message": "Officer deleted"}


@router.patch("/officers/{officer_id}/toggle")
def toggle_officer(
    officer_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    o = db.query(FieldOfficer).filter(FieldOfficer.id == officer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Officer not found")
    o.is_active = not o.is_active
    db.commit()
    return {"message": "Toggled", "is_active": o.is_active}


# ── Citizens ──────────────────────────────────────────────────────────────────

@router.get("/citizens")
def list_citizens(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    users = db.query(User).all()
    result = []
    for u in users:
        c_all  = db.query(Complaint).filter(Complaint.user_id == u.id).all()
        total  = len(c_all)
        done   = sum(1 for c in c_all if c.status == "completed")
        hi_sev = sum(1 for c in c_all if c.severity == "high")
        result.append({
            "id":            u.id,
            "name":          u.name,
            "email":         u.email,
            "phone":         u.phone or "",
            "is_active":     u.is_active,
            "created_at":    u.created_at.isoformat() if u.created_at else "",
            # exact names admin.html renders:
            "total_reports": total,
            "completed":     done,
            "fixed":         done,
            "high_severity": hi_sev,
            "points":        u.reward_points or 0,
            "reward_points": u.reward_points or 0,
        })
    return result


@router.delete("/citizens/{citizen_id}")
def delete_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    u = db.query(User).filter(User.id == citizen_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Citizen not found")
    db.delete(u)
    db.commit()
    return {"message": "Deleted"}


@router.patch("/citizens/{citizen_id}/toggle")
def toggle_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    u = db.query(User).filter(User.id == citizen_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Citizen not found")
    u.is_active = not u.is_active
    db.commit()
    return {"message": "Toggled", "is_active": u.is_active}


@router.patch("/citizens/{citizen_id}")
def edit_citizen(
    citizen_id: int,
    payload: CitizenEdit,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    u = db.query(User).filter(User.id == citizen_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Citizen not found")
    
    if payload.name is not None:
        u.name = payload.name
    if payload.email is not None:
        u.email = payload.email
    if payload.phone is not None:
        u.phone = payload.phone
    if payload.points is not None:
        u.reward_points = payload.points
    if payload.password is not None and payload.password.strip() != "":
        u.hashed_password = pwd_ctx.hash(payload.password)
        
    db.commit()
    return {"message": "Updated"}


@router.post("/citizens/{citizen_id}/block")
def block_citizen(
    citizen_id: int,
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    u = db.query(User).filter(User.id == citizen_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Citizen not found")
    u.is_active = False
    db.commit()
    return {"message": "Blocked"}


# ── Login Logs ────────────────────────────────────────────────────────────────

def _iso_dt(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


@router.get("/login-logs")
def admin_login_logs(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    """GET /api/admin/login-logs — returns all login logs"""
    rows = db.query(LoginLog).order_by(LoginLog.logged_in_at.desc()).limit(200).all()
    return [{
        "id": r.id,
        "email": r.email,
        "role": r.role,
        "ip_address": r.ip_address,
        "logged_in_at": _iso_dt(r.logged_in_at),
        "logged_out_at": _iso_dt(r.logged_out_at),
        "session_minutes": r.session_minutes,
    } for r in rows]


# ── Chart ─────────────────────────────────────────────────────────────────────

@router.get("/chart/daily")
def chart_daily(
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    result = []
    today = datetime.now(timezone.utc).date()
    for i in range(6, -1, -1):
        day   = today - timedelta(days=i)
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end   = start + timedelta(days=1)
        count = db.query(Complaint).filter(
            Complaint.created_at >= start,
            Complaint.created_at < end,
        ).count()
        result.append({"date": day.strftime("%b %d"), "count": count})
    return result


# ── PDF Report Generation ───────────────────────────────────────────────────

class RoadWatchPDF(FPDF):
    def header(self):
        self.set_fill_color(10, 12, 16) # Dark background for header
        self.rect(0, 0, 210, 30, 'F')
        self.set_font("helvetica", "B", 20)
        self.set_text_color(245, 166, 35) # Accent orange
        self.cell(0, 20, "ROADWATCH SYSTEM REPORT", align="C", ln=True)
        self.set_font("helvetica", "I", 10)
        self.set_text_color(107, 118, 148) # Muted text
        self.cell(0, -5, f"Generated on: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M %Z')}", align="C", ln=True)
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()} / {{nb}} -- Confidential RoadWatch Internal Document", align="C")

@router.get("/reports/download")
def download_pdf_report(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    _: FieldOfficer = Depends(get_current_admin),
):
    query = db.query(Complaint)
    if status and status != "all":
        query = query.filter(Complaint.status == status)
    if severity and severity != "all":
        query = query.filter(Complaint.severity == severity)
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.filter(Complaint.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            query = query.filter(Complaint.created_at <= dt_to)
        except ValueError:
            pass
    
    complaints = query.order_by(Complaint.created_at.desc()).all()
    
    pdf = RoadWatchPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    try:
        if not complaints:
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(0, 20, "No complaints found matching current filters.", align="C")
        else:
            for c in complaints:
                # Check if we need a new page for image + info
                if pdf.get_y() > 200:
                    pdf.add_page()

                # ID Row
                pdf.set_fill_color(24, 29, 39)
                pdf.rect(10, pdf.get_y(), 190, 10, 'F')
                pdf.set_font("helvetica", "B", 12)
                pdf.set_text_color(255, 255, 255)
                cid = c.complaint_id or f"RD-{c.id:06d}"
                pdf.cell(100, 10, f"  COMPLAINT: {cid}", ln=False)
                
                # Status badge color
                pdf.set_font("helvetica", "B", 9)
                if c.status == "completed": pdf.set_text_color(62, 207, 178)
                elif c.status == "rejected": pdf.set_text_color(224, 92, 92)
                else: pdf.set_text_color(245, 166, 35)
                pdf.cell(90, 10, f"STATUS: {str(c.status).upper()}   ", align="R", ln=True)

                pdf.ln(2)
                y_start = pdf.get_y()

                # Image logic
                img_drawn = False
                if c.image_url:
                    # Local path for images
                    img_path = "." + c.image_url # Assuming /uploads/...
                    if os.path.exists(img_path):
                        try:
                            pdf.image(img_path, x=10, y=y_start, w=70)
                            img_drawn = True
                        except Exception as img_err:
                            print(f"PDF Image Error: {img_err}")
                
                x_offset = 85 if img_drawn else 15
                pdf.set_text_color(50)
                
                # Data Grid
                pdf.set_xy(x_offset, y_start)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(30, 6, "Damage Type:")
                pdf.set_font("helvetica", "", 10)
                pdf.cell(0, 6, str(c.damage_type).title(), ln=True)

                pdf.set_x(x_offset)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(30, 6, "Severity:")
                pdf.set_font("helvetica", "B", 10)
                if c.severity == "high": pdf.set_text_color(224, 92, 92)
                else: pdf.set_text_color(100)
                pdf.cell(0, 6, str(c.severity).upper(), ln=True)
                pdf.set_text_color(50)

                pdf.set_x(x_offset)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(30, 6, "Created On:")
                pdf.set_font("helvetica", "", 10)
                ts = c.created_at.strftime('%d %b %Y, %I:%M %p') if c.created_at else "N/A"
                pdf.cell(0, 6, ts, ln=True)

                pdf.set_x(x_offset)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(30, 6, "GPS Coordinates:")
                pdf.set_font("helvetica", "", 10)
                pdf.cell(0, 6, f"{c.latitude:.5f}, {c.longitude:.5f}", ln=True)

                # Address - multi-line
                pdf.set_x(x_offset)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(30, 6, "Location:")
                pdf.set_font("helvetica", "", 9)
                addr_text = (c.address or "No address provided").encode("ascii", "ignore").decode("ascii")
                pdf.multi_cell(0, 5, addr_text)

                # Description - multi-line
                pdf.set_x(x_offset)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(30, 6, "Description:")
                pdf.set_font("helvetica", "", 9)
                desc_text = (c.description or "No description provided").encode("ascii", "ignore").decode("ascii")
                pdf.multi_cell(0, 5, desc_text)

                # Officer Info
                pdf.ln(2)
                pdf.set_x(x_offset)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(30, 6, "Officer:")
                pdf.set_font("helvetica", "I", 10)
                off_name = "Unassigned"
                if c.officer_id:
                    off = db.query(FieldOfficer).filter(FieldOfficer.id == c.officer_id).first()
                    if off: off_name = off.name
                pdf.cell(0, 6, off_name.encode("ascii", "ignore").decode("ascii"), ln=True)

                pdf.ln(10)
                if pdf.get_y() < y_start + 50 and img_drawn:
                    pdf.set_y(y_start + 55)
                
                # Divider
                pdf.set_draw_color(230)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(5)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF Error: {str(e)}")

    buffer = io.BytesIO()
    pdf_out = pdf.output()
    buffer.write(pdf_out)
    buffer.seek(0)
    
    filename = f"RoadWatch_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )