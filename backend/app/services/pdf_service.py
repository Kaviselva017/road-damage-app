import io
import httpx
import logging
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from sqlalchemy import select
from app.models.models import FieldOfficer, AuditLog

logger = logging.getLogger(__name__)

async def _fetch_image(url: str):
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return io.BytesIO(resp.content)
    except Exception as e:
        logger.error(f"Failed to fetch image from {url}: {e}")
    return None

def _header_footer(canvas, doc, complaint_id):
    canvas.saveState()
    styles = getSampleStyleSheet()
    
    # Footer
    footer = f"Page {doc.page} | Complaint ID: {complaint_id} | This document is computer-generated and legally valid"
    canvas.setFont('Helvetica', 8)
    canvas.drawCentredString(A4[0]/2, 0.5*inch, footer)
    
    canvas.restoreState()

async def generate_complaint_pdf(complaint, audit_logs: list[AuditLog], db) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=50, leftMargin=50,
        topMargin=50, bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey,
        spaceAfter=20
    )
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        borderPadding=5,
        textColor=colors.darkblue
    )
    
    elements = []
    
    # --- PAGE 1: HEADER ---
    elements.append(Paragraph("RoadWatch — Official Road Damage Report", title_style))
    elements.append(Paragraph("Government of Tamil Nadu | Municipal Civic Portal", subtitle_style))
    
    header_data = [
        [f"Report ID: {complaint.complaint_id}", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
        ["Classification: OFFICIAL USE ONLY", ""]
    ]
    header_table = Table(header_data, colWidths=[3*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.grey),
        ('ALIGN', (1,0), (1,1), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceBefore=5, spaceAfter=20))
    
    # --- SECTION 1: Complaint Details ---
    elements.append(Paragraph("SECTION 1: Complaint Details", section_style))
    
    # Fetch officer name if available
    officer_name = "Not Assigned"
    if complaint.officer_id:
        stmt = select(FieldOfficer).where(FieldOfficer.id == complaint.officer_id)
        result = await db.execute(stmt)
        officer = result.scalar_one_or_none()
        if officer:
            officer_name = officer.name

    details_data = [
        ["Field", "Value"],
        ["Complaint ID", complaint.complaint_id],
        ["Submission Date", complaint.created_at.strftime('%Y-%m-%d %H:%M:%S')],
        ["Location (Lat, Lng)", f"{complaint.latitude:.5f}, {complaint.longitude:.5f}"],
        ["Address", complaint.address or "N/A"],
        ["AI Damage Type", complaint.damage_type or "N/A"],
        ["AI Confidence", f"{(complaint.ai_confidence or 0.0) * 100:.1f}%"],
        ["Severity", (complaint.severity or "N/A").upper()],
        ["Priority Score", f"{complaint.priority_score or 0.0:.1f} / {complaint.urgency_label or 'N/A'}"],
        ["Current Status", (complaint.status or "N/A").replace('_', ' ').title()],
        ["Assigned Officer", officer_name],
        ["Resolved Date", complaint.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.resolved_at else "Pending"]
    ]
    
    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke])
    ]))
    elements.append(details_table)
    
    # --- SECTION 2: Road Damage Photo ---
    elements.append(Paragraph("SECTION 2: Road Damage Photograph", section_style))
    img_data = await _fetch_image(complaint.image_url)
    if img_data:
        try:
            img = Image(img_data)
            # Max width 400 points, max height 300 points
            img.drawWidth = 400
            img.drawHeight = 300
            # Correct aspect ratio
            aspect = img.imageWidth / img.imageHeight
            if aspect > 400/300:
                img.drawHeight = 400 / aspect
            else:
                img.drawWidth = 300 * aspect
            elements.append(img)
        except Exception:
            elements.append(Paragraph("[Error rendering image]", styles['Normal']))
    else:
        elements.append(Paragraph("Image unavailable", styles['Normal']))
    
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Figure 1: AI-analyzed road damage photograph", subtitle_style))
    
    # --- SECTION 3: AI Analysis Summary ---
    elements.append(Paragraph("SECTION 3: AI Analysis Summary", section_style))
    
    # Recommended Action
    actions = {
        "pothole": "Immediate patching required",
        "crack": "Surface sealing recommended",
        "subsidence": "URGENT: Structural assessment required",
        "flooding": "Drainage inspection required"
    }
    recommended_action = actions.get((complaint.damage_type or "").lower(), "Field assessment required")
    
    # Confidence Bar
    conf = (complaint.ai_confidence or 0.0)
    conf_pct = conf * 100
    
    elements.append(Paragraph(f"<b>AI Confidence: {conf_pct:.1f}%</b>", styles['Normal']))
    elements.append(Spacer(1, 5))
    
    # Progress bar using a 2-column table
    filled_w = max(0.01, 4 * conf)
    empty_w = max(0.01, 4 * (1 - conf))
    bar_color = colors.green if conf > 0.7 else (colors.orange if conf > 0.4 else colors.red)
    
    bar_table = Table([["", ""]], colWidths=[filled_w*inch, empty_w*inch], rowHeights=[15])
    bar_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), bar_color),
        ('BACKGROUND', (1, 0), (1, 0), colors.lightgrey),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(bar_table)
    
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Severity Assessment: <b>{(complaint.severity or 'N/A').upper()}</b>", styles['Normal']))
    elements.append(Paragraph(f"Recommended Action: <i>{recommended_action}</i>", styles['Normal']))

    # --- SECTION 4: Audit Trail ---
    elements.append(Paragraph("SECTION 4: Official Audit Trail", section_style))
    audit_data = [["Timestamp", "Action", "Actor", "Role", "IP"]]
    for log in audit_logs[:10]:
        audit_data.append([
            log.created_at.strftime('%Y-%m-%d %H:%M'),
            log.action,
            str(log.actor_id or "System"),
            log.actor_role or "-",
            log.ip_address or "-"
        ])
    
    if len(audit_data) > 1:
        audit_table = Table(audit_data, colWidths=[1.2*inch, 1.2*inch, 1*inch, 1*inch, 1.6*inch])
        audit_table.setStyle(TableStyle([
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        elements.append(audit_table)
    else:
        elements.append(Paragraph("No audit logs available for this complaint.", styles['Normal']))

    def on_page(canvas, doc):
        _header_footer(canvas, doc, complaint.complaint_id)
        
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    return buffer.getvalue()

async def generate_bulk_pdf(complaints: list, db) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=50, leftMargin=50,
        topMargin=50, bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER)
    
    elements = []
    
    # Cover Page
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("RoadWatch Bulk Export Report", title_style))
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Paragraph(f"Total Complaints: {len(complaints)}", styles['Normal']))
    
    # Status Summary
    stats = {}
    for c in complaints:
        stats[c.status] = stats.get(c.status, 0) + 1
    
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("<b>Status Summary:</b>", styles['Normal']))
    for stat, count in stats.items():
        elements.append(Paragraph(f"• {stat.replace('_', ' ').title()}: {count}", styles['Normal']))
    
    # Table of Contents
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("<b>Complaints List:</b>", styles['Normal']))
    for i, c in enumerate(complaints):
        elements.append(Paragraph(f"{i+1}. {c.complaint_id} — {c.damage_type} ({c.status})", styles['Normal']))
    
    elements.append(PageBreak())
    
    # Each complaint: condensed 1-page summary
    for c in complaints:
        elements.append(Paragraph(f"Complaint: {c.complaint_id}", styles['Heading2']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        
        details = [
            ["Status", c.status.replace('_', ' ').title()],
            ["Severity", c.severity.upper()],
            ["Type", c.damage_type],
            ["Priority", f"{c.priority_score:.1f}"],
            ["Location", f"{c.latitude:.4f}, {c.longitude:.4f}"],
            ["Created", c.created_at.strftime('%Y-%m-%d')]
        ]
        t = Table(details, colWidths=[1.5*inch, 4*inch])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
        elements.append(t)
        
        # Image if available
        img_data = await _fetch_image(c.image_url)
        if img_data:
            try:
                img = Image(img_data)
                img.drawWidth = 200
                img.drawHeight = 150
                elements.append(Spacer(1, 10))
                elements.append(img)
            except Exception:
                pass
        
        elements.append(PageBreak())

    doc.build(elements)
    return buffer.getvalue()
