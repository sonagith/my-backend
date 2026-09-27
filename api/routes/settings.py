# Backend/api/routes/settings.py
from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from api.deps import get_db
from db import models

router = APIRouter()

@router.get("/get-all")
def get_all_settings(db: Session = Depends(get_db)):
    profile = db.query(models.BusinessProfile).first()
    if not profile:
        profile = models.BusinessProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)

    staff = db.query(models.Staff).all()
    if not staff:
        default_staff = [
            models.Staff(name="Anil Kumar Nair", role="Recovery Officer", phone="+91 98470 11223"),
            models.Staff(name="Priya Subramaniam", role="Senior Sales Manager", phone="+91 98470 55667"),
            models.Staff(name="Deepak Menon", role="Recovery Officer", phone="+91 98470 99881")
        ]
        db.add_all(default_staff)
        db.commit()
        staff = db.query(models.Staff).all()

    automation = db.query(models.AutomationSettings).first()
    if not automation:
        automation = models.AutomationSettings()
        db.add(automation)
        db.commit()
        db.refresh(automation)

    return {"status": "success", "profile": profile, "staff": staff, "automation": automation}

@router.post("/update-profile")
def update_profile(
    business_name: str = Form(...), owner_name: str = Form(...), phone_number: str = Form(...),
    industry: str = Form(...), gstin: str = Form(...), pan: str = Form(...),
    city: str = Form(...), state: str = Form(...), pin_code: str = Form(...), rera_no: str = Form(...),
    db: Session = Depends(get_db)
):
    profile = db.query(models.BusinessProfile).first()
    profile.business_name = business_name
    profile.owner_name = owner_name
    profile.phone_number = phone_number
    profile.industry = industry
    profile.gstin = gstin
    profile.pan = pan
    profile.city = city
    profile.state = state
    profile.pin_code = pin_code
    profile.rera_no = rera_no
    db.commit()
    return {"status": "success"}

@router.post("/add-staff")
def add_staff(name: str = Form(...), role: str = Form(...), phone: str = Form(...), db: Session = Depends(get_db)):
    new_staff = models.Staff(name=name, role=role, phone=phone)
    db.add(new_staff)
    db.commit()
    return {"status": "success"}

@router.post("/update-automation")
def update_auto(
    sms_day: int = Form(...), sms_on: int = Form(...), wa_day: int = Form(...), wa_on: int = Form(...),
    escalate_day: int = Form(...), escalate_on: int = Form(...), db: Session = Depends(get_db)
):
    auto = db.query(models.AutomationSettings).first()
    auto.sms_day = sms_day
    auto.sms_on = sms_on
    auto.wa_day = wa_day
    auto.wa_on = wa_on
    auto.escalate_day = escalate_day
    auto.escalate_on = escalate_on
    db.commit()
    return {"status": "success"}

@router.get("/templates")
def get_templates(db: Session = Depends(get_db)):
    templates = db.query(models.MessageTemplate).all()
    if not templates:
        defaults = [
            {"key": "upcoming", "title": "Upcoming Installment Reminder", "sub": "Sent 3 days before the due date", "ico": "🔔", "bg": "var(--blue-bg)", "color": "var(--blue)", "subj": "Upcoming Installment - {{invoiceNumber}}", "body": "Dear {{clientName}},\n\nThis is a friendly reminder that your installment of {{installmentAmount}} for plot {{plotNumber}} is due on {{dueDate}}.\n\nOutstanding Balance: {{outstandingBalance}}\n\nPlease make the payment at your earliest convenience.\n{{paymentLink}}\n\n- {{vendorName}}"},
            {"key": "sms", "title": "SMS Reminder (Day 11)", "sub": "Sent automatically 11 days after the due date", "ico": "💬", "bg": "var(--orange-bg)", "color": "var(--orange)", "subj": "Payment Reminder - {{invoiceNumber}}", "body": "Dear {{clientName}}, your installment of {{installmentAmount}} for plot {{plotNumber}} was due on {{dueDate}} and remains unpaid. Outstanding balance: {{outstandingBalance}}. Pay now: {{paymentLink}} - {{vendorName}}"},
            {"key": "whatsapp", "title": "WhatsApp Reminder (Day 13)", "sub": "Sent automatically 13 days after the due date", "ico": "📱", "bg": "var(--orange-bg)", "color": "var(--orange)", "subj": "Payment Reminder - {{invoiceNumber}}", "body": "Hi {{clientName}}, this is a reminder from {{vendorName}} that your plot {{plotNumber}} installment of {{installmentAmount}} is still pending.\n\nDue Date: {{dueDate}}\nOutstanding Balance: {{outstandingBalance}}\n\nPlease complete your payment here: {{paymentLink}}\n\nIf you have already paid, kindly ignore this message."},
            {"key": "escalate", "title": "Staff Escalation Alert (Day 16+)", "sub": "Internal alert sent to the assigned recovery officer", "ico": "✋", "bg": "var(--red-bg)", "color": "var(--red)", "subj": "Escalation Alert - {{invoiceNumber}}", "body": "Case escalated: {{clientName}} (Plot {{plotNumber}}) has an overdue installment of {{installmentAmount}}, due {{dueDate}}. Outstanding balance: {{outstandingBalance}}.\n\nPlease contact the client directly.\nAssigned to: {{staffName}} ({{staffPhone}})"}
        ]
        for d in defaults:
            db.add(models.MessageTemplate(template_key=d["key"], title=d["title"], subtitle=d["sub"], icon=d["ico"], bg_color=d["bg"], text_color=d["color"], subject=d["subj"], body=d["body"], is_enabled=1))
        db.commit()
        templates = db.query(models.MessageTemplate).all()

    # Database se placeholders fetch karke correct mapping bhej rahe hain
    placeholders_db = db.query(models.PlaceholderRef).all()
    phs = [
        {
            "ph_key": p.ph_key, 
            "description": p.description, 
            "sample_value": p.sample_value
        } for p in placeholders_db
    ]

    return {
        "status": "success", 
        "templates": templates, 
        "placeholders": phs
    }

@router.post("/update-template")
def update_template(
    template_key: str = Form(...), subject: str = Form(...), body: str = Form(...), is_enabled: int = Form(...),
    db: Session = Depends(get_db)
):
    t = db.query(models.MessageTemplate).filter(models.MessageTemplate.template_key == template_key).first()
    if t:
        t.subject = subject
        t.body = body
        t.is_enabled = is_enabled
        db.commit()
        return {"status": "success"}
    return {"status": "error", "message": "Template not found"}

@router.post("/add-placeholder")
def add_placeholder(ph_key: str = Form(...), description: str = Form(...), sample_value: str = Form(...), db: Session = Depends(get_db)):
    exists = db.query(models.PlaceholderRef).filter(models.PlaceholderRef.ph_key == ph_key).first()
    if exists:
        return {"status": "error", "message": "Placeholder key already exists"}
    
    new_ph = models.PlaceholderRef(ph_key=ph_key, description=description, sample_value=sample_value)
    db.add(new_ph)
    db.commit()
    return {"status": "success"}


# Backend/api/routes/settings.py ke end mein:
from core.automation import run_daily_reminders

@router.post("/trigger-automation-test")
def test_automation():
    """Sirf testing ke liye. Manual trigger background cron job."""
    run_daily_reminders()
    return {"status": "success", "message": "Automation job triggered! Check backend console."}


from fastapi import APIRouter, Depends, Form, UploadFile, File
from sqlalchemy.orm import Session
from api.deps import get_db
from db import models
import shutil
import os

# ... aapka baaki ka code ...

# 🔴 NAYI API - LOGO UPLOAD KARNE KE LIYE 🔴
@router.post("/upload-logo")
def upload_logo(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Folder create karein agar nahi hai toh
    os.makedirs("uploads/logos", exist_ok=True)
    
    # 2. File ko save karein
    file_path = f"uploads/logos/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. Database mein URL update karein
    profile = db.query(models.BusinessProfile).first()
    if profile:
        profile.logo_url = f"/{file_path}"
        db.commit()
        
    return {
        "status": "success", 
        "message": "Logo uploaded successfully", 
        "logo_url": f"/{file_path}"
    }