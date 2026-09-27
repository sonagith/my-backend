# Backend/api/routes/dashboard.py
from sqlalchemy.orm import Session
from api.deps import get_db, get_current_user
from db import models
from datetime import date
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
import pandas as pd
import io
import shutil
import uuid
import os
from datetime import datetime

router = APIRouter()

def get_next_4th(current_date):
    if not current_date: return None
    if current_date.month == 12:
        return date(current_date.year + 1, 1, 4)
    else:
        return date(current_date.year, current_date.month + 1, 4)

# 🔴 HELPER FUNCTION FOR AUDIT HISTORY
def log_activity(db: Session, plot_id: int, title: str, description: str):
    new_log = models.ActivityLog(
        plot_id=plot_id, 
        date=date.today(),
        title=title, 
        description=description
    )
    db.add(new_log)
    db.commit()

# 🔴 1. GET ALL DATA ROUTE (FIXED FOR KYC, URLs & STAFF) 🔴
@router.get("/all-data")
def get_dashboard_data(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    plots = db.query(models.Plot).all()
    projects_db = db.query(models.Project).all()
    
    projects = [{
        "id": str(p.id), 
        "name": p.name, 
        "location": p.location if hasattr(p, 'location') and p.location else "India", 
        "plotPrefix": p.plotPrefix if hasattr(p, 'plotPrefix') and p.plotPrefix else "P", 
        "targetClients": p.targetClients if hasattr(p, 'targetClients') and p.targetClients is not None else len(p.plots)
    } for p in projects_db]
    
    if not projects: 
        projects = [{"id": '1', "name": 'Default Project', "location": 'India', "plotPrefix": 'A', "targetClients": 100}]

    cases = []
    
    for p in plots:
        client = p.client
        payments = p.payments
        
        pay_list = []
        total_paid = 0
        last_payment_date = None
        
        for idx, pay in enumerate(payments):
            amt = pay.amount or 0
            total_paid += amt
            pay_list.append({
                "rn": idx + 1,
                "date": pay.date.isoformat() if pay.date else "",
                "amount": amt,
                "chNo": pay.cheque_no or "—",
                "receivedDate": pay.date.isoformat() if pay.date else "",
                "bankName": pay.drawn_on or "—",
                "remark": pay.remarks or "—",
                "drawnOn": pay.drawn_on or "—",
                "chDate": pay.ch_date.isoformat() if pay.ch_date else "—",
                "bookedBy": pay.booked_by or "—",
                "receiptUrl": pay.receipt_url 
            })
            if pay.date:
                if not last_payment_date or pay.date > last_payment_date:
                    last_payment_date = pay.date
        
        plot_val = p.plot_value or 0
        balance = plot_val - total_paid
        status = "resolved" if balance <= 0 else "open"
        
        calculated_due_date = ""
        if balance > 0:
            base_date = last_payment_date if last_payment_date else p.sale_date
            if base_date:
                calculated_due_date = get_next_4th(base_date).isoformat()

        doc_list = [{"id": d.id, "name": d.document_name, "url": d.document_url} for d in p.documents] if p.documents else []
        
        cases.append({
            "id": p.id,
            "code": f"RC-{str(p.id).zfill(5)}",
            "status": status,
            "projectId": str(p.project_id) if p.project_id else "1",
            "buyer": {
                "id": client.id if client else None,
                "name": client.name if client else "Unknown",
                "phone": client.contact_no if client else "—",
                "email": client.email or "—",
                "address": client.address or "—",
                "pan": client.pan_card or "—",
                "aadhaar": client.aadhaar_card if getattr(client, 'aadhaar_card', None) else "—",
                "nationalId": getattr(client, 'national_id', "—"),
                "panDocUrl": getattr(client, 'pan_doc_url', None),
                "aadhaarDocUrl": getattr(client, 'aadhaar_doc_url', None),
                "nationalIdDocUrl": getattr(client, 'national_id_doc_url', None)
            },
            "plot": {
                "plotNumber": p.plot_no or f"Plot-{p.id}",
                "project": p.project.name if p.project else "Default Project",
                "extentSqft": p.plot_size_sqft or 0,
                "ratePerSqft": p.rate or 0,
                "totalValue": plot_val,
                "bookingDate": p.sale_date.isoformat() if p.sale_date else "",
                "endDate": p.end_date.isoformat() if getattr(p, 'end_date', None) else "",
                "agreementNo": f"AGR-{p.plot_no}",
                "registrationStatus": p.registration_status or "Pending",
                "surveyNumber": p.survey_number or "—",
                "facing": p.facing or "—",
                "bookedBy": p.booked_by or "—",
                "commissionPerSqft": p.commission_per_sqft or 0.0,
                "totalCommission": p.total_commission or 0.0,
                "commissionPaidAmount": p.commission_paid_amount or 0.0,
                "documents": doc_list,
                "assignedStaff": {
                    "id": p.assigned_staff.id if p.assigned_staff else None,
                    "name": p.assigned_staff.name if p.assigned_staff else "Unassigned",
                    "role": p.assigned_staff.role if p.assigned_staff else "Staff",
                    "phone": p.assigned_staff.phone if p.assigned_staff else "—",
                    "email": p.assigned_staff.email if p.assigned_staff else "—"
                } if p.assigned_staff else None
            },
            "assignedStaffId": p.assigned_staff_id or 1,
            "dueDate": calculated_due_date,
            "installmentAmount": p.monthly_emi if p.monthly_emi else (balance if balance > 0 else 0),
            "totalDp": p.total_dp,
            "payments": pay_list,
            "activity": [
                {
                    "date": act.date.isoformat() if act.date else "",
                    "title": act.title,
                    "desc": act.description
                } for act in getattr(p, 'activities', [])
            ][::-1] 
        })

    profile = db.query(models.BusinessProfile).first()
    if not profile:
        profile = models.BusinessProfile(owner_name="Ramesh", business_name="Mehta Realty Group")
        db.add(profile)
        db.commit()
        db.refresh(profile)

    integrations_db = db.query(models.Integration).all()
    if not integrations_db:
        defaults = [
            {"name": "Zoho Books", "desc": "Sync invoices & payments", "icon": "💾", "conn": 0},
            {"name": "Tally ERP", "desc": "Auto-import ledgers & overdue bills", "icon": "💳", "conn": 0},
            {"name": "Razorpay", "desc": "Collect installments online & reconcile", "icon": "⚡", "conn": 0},
            {"name": "WhatsApp Business API", "desc": "Send reminders & payment links", "icon": "📱", "conn": 1},
            {"name": "Retell AI", "desc": "Bilingual voice agent for overdue calls", "icon": "🔊", "conn": 1},
            {"name": "SMS Gateway (MSG91)", "desc": "Automated SMS reminders", "icon": "💬", "conn": 1},
            {"name": "Salesforce", "desc": "CRM & opportunity sync", "icon": "☁️", "conn": 0},
            {"name": "Custom Webhook", "desc": "Connect any external system", "icon": "🔗", "conn": 0},
        ]
        for d in defaults:
            db.add(models.Integration(name=d["name"], description=d["desc"], icon=d["icon"], is_connected=d["conn"]))
        db.commit()
        integrations_db = db.query(models.Integration).all()

    profile_data = {
        "owner_name": profile.owner_name if profile.owner_name else "", 
        "business_name": profile.business_name if profile.business_name else "",
        "logo_url": profile.logo_url if profile.logo_url else ""
    }
    integration_list = [{"id": i.id, "name": i.name, "description": i.description, "icon": i.icon, "isConnected": bool(i.is_connected)} for i in integrations_db]

    return {
        "status": "success", 
        "projects": projects, 
        "cases": cases,
        "profile": profile_data,
        "integrations": integration_list
    }


# 🔴 2. PROJECT ROUTES 🔴
@router.post("/add-project")
def add_project(name: str = Form(...), location: str = Form(...), plotPrefix: str = Form(...), targetClients: int = Form(...), db: Session = Depends(get_db)):
    new_project = models.Project(name=name, location=location, plotPrefix=plotPrefix, targetClients=targetClients)
    db.add(new_project)
    db.commit()
    return {"status": "success", "message": "Project added successfully"}

@router.post("/update-project")
def update_project(id: int = Form(...), name: str = Form(...), location: str = Form(...), plotPrefix: str = Form(...), targetClients: int = Form(...), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    
    project.name = name; project.location = location; project.plotPrefix = plotPrefix; project.targetClients = targetClients
    db.commit()
    return {"status": "success", "message": "Project updated successfully"}

@router.post("/delete-project")
def delete_project(id: int = Form(...), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == id).first()
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    if project.plots: return {"status": "error", "message": "Cannot delete project. It has registered clients!"}
    db.delete(project); db.commit()
    return {"status": "success", "message": "Project deleted successfully"}


# 🔴 3. EXCEL IMPORT ROUTE 🔴
def parse_float(val):
    if pd.isna(val) or val is None: return 0.0
    s = str(val).replace(',', '').replace('₹', '').replace('Rs', '').strip()
    if not s or s.lower() in ['nan', '-', 'none', 'null']: return 0.0
    try: return float(s)
    except: return 0.0

def parse_str(val):
    if pd.isna(val) or val is None: return ""
    s = str(val).strip()
    if s.lower() in ['nan', 'none', 'null', 'nat']: return ""
    return s

def parse_date(val):
    if pd.isna(val) or val is None or str(val).strip() == "": return None
    try: return pd.to_datetime(val, dayfirst=True).date()
    except: return None

@router.post("/import-excel")
async def import_excel_data(project_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        contents = await file.read()
        xls = pd.ExcelFile(io.BytesIO(contents))
        sheet_name = "Import_Data" if "Import_Data" in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(xls, sheet_name=sheet_name)

        imported_count = 0; skipped_count = 0; failed_rows = []

        for index, row in df.iterrows():
            try:
                raw_plot = parse_str(row.get("Plot Number"))
                if raw_plot.endswith('.0'): raw_plot = raw_plot[:-2] 
                plot_no = raw_plot

                if not plot_no:
                    skipped_count += 1
                    failed_rows.append({"row": index + 2, "reason": "Missing Plot Number"})
                    continue
                
                client_name = parse_str(row.get("Buyer Name")) or "Unknown Client"
                client_phone = parse_str(row.get("Phone"))
                client_email = parse_str(row.get("Email"))
                client_address = parse_str(row.get("Address"))
                
                client = db.query(models.Client).filter(models.Client.name == client_name, models.Client.contact_no == client_phone).first()
                if not client:
                    client = models.Client(name=client_name, contact_no=client_phone, email=client_email, address=client_address)
                    db.add(client)
                    db.commit()
                    db.refresh(client)

                plot = db.query(models.Plot).filter(models.Plot.plot_no == plot_no, models.Plot.project_id == project_id).first()
                due_dt = parse_date(row.get("Next Due Date"))
                booking_dt = parse_date(row.get("Booking Date"))
                
                if not plot:
                    plot = models.Plot(
                        plot_no=plot_no, project_id=project_id, client_id=client.id,
                        plot_size_sqft=parse_float(row.get("Extent (SqFt)")), rate=parse_float(row.get("Rate/SqFt")),
                        plot_value=parse_float(row.get("Total Plot Value")), total_dp=parse_float(row.get("Total DP")),
                        monthly_emi=parse_float(row.get("Installment Amount")), due_date=due_dt, sale_date=booking_dt, 
                        total_due_balance=parse_float(row.get("Due Balance"))
                    )
                    db.add(plot)
                    db.commit()
                    db.refresh(plot)

                amt = parse_float(row.get("Amount"))
                if amt > 0:
                    pay_dt = parse_date(row.get("Payment Date"))
                    chq = parse_str(row.get("Ref/Cheque No"))
                    exist_pay = db.query(models.Payment).filter(
                        models.Payment.plot_id == plot.id, models.Payment.amount == amt,
                        models.Payment.date == pay_dt, models.Payment.cheque_no == chq
                    ).first()
                    
                    if not exist_pay:
                        db.add(models.Payment(
                            plot_id=plot.id, date=pay_dt, amount=amt,
                            drawn_on=parse_str(row.get("Mode/Bank")), cheque_no=chq,
                            remarks=parse_str(row.get("Remarks"))
                        ))
                imported_count += 1
            except Exception as e:
                skipped_count += 1
                failed_rows.append({"row": index + 2, "reason": str(e)})
        
        db.commit()
        return {"status": "success", "message": f"Successfully processed {imported_count} rows.", "summary": {"imported": imported_count, "skipped": skipped_count, "failed_details": failed_rows}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"File Processing Error: {str(e)}")


# 🔴 4. PLOT INFO UPDATE & DOCUMENTS ROUTES (WITH AUDIT) 🔴
@router.post("/update-plot-info")
def update_plot_information(
    plot_id: int = Form(...), plot_number: str = Form(None), survey_number: str = Form(None),
    extent: float = Form(None), facing: str = Form(None), rate: float = Form(None),
    total_dp: float = Form(None), monthly_emi: float = Form(None), registration_status: str = Form(None),
    booking_date: str = Form(None), # <--- NAYA
    end_date: str = Form(None),     # <--- NAYA
    db: Session = Depends(get_db)
):
    plot = db.query(models.Plot).filter(models.Plot.id == plot_id).first()
    if not plot: raise HTTPException(status_code=404, detail="Plot not found")

    if plot_number is not None: plot.plot_no = plot_number
    if survey_number is not None: plot.survey_number = survey_number
    if extent is not None: plot.plot_size_sqft = extent
    if facing is not None: plot.facing = facing
    if rate is not None: plot.rate = rate
    if total_dp is not None: plot.total_dp = total_dp
    if monthly_emi is not None: plot.monthly_emi = monthly_emi
    if registration_status is not None: plot.registration_status = registration_status

    # 🔴 NAYA LOGIC DATE UPDATE KE LIYE (WITH 2 YEARS LOGIC)
    if booking_date:
        try:
            plot.sale_date = datetime.strptime(booking_date, "%Y-%m-%d").date()
            # Agar end_date nahi hai, toh automatically booking_date + 2 years set kardo
            if not end_date and not plot.end_date:
                try:
                    plot.end_date = plot.sale_date.replace(year=plot.sale_date.year + 2)
                except ValueError:
                    plot.end_date = plot.sale_date.replace(year=plot.sale_date.year + 2, day=28) # Leap year safe
        except Exception:
            pass

    if end_date:
        try:
            plot.end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception:
            pass

    plot.plot_value = float(plot.plot_size_sqft or 0) * float(plot.rate or 0)
    db.commit()
    log_activity(db, plot_id, "Plot Info Updated", "Basic plot details were modified.")
    return {"status": "success", "message": "Plot details updated successfully"}

@router.post("/upload-plot-document")
async def upload_plot_doc(
    plot_id: int = Form(...), doc_name: str = Form(...), file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    plot = db.query(models.Plot).filter(models.Plot.id == plot_id).first()
    if not plot: raise HTTPException(status_code=404, detail="Plot not found")

    file_ext = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = f"uploads/documents/{unique_filename}"
    
    with open(file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    full_url = f"http://localhost:8000/{file_path}"
    new_doc = models.PlotDocument(plot_id=plot.id, document_name=doc_name, document_url=full_url)
    db.add(new_doc)
    db.commit()
    log_activity(db, plot_id, "Document Uploaded", f"Uploaded: {doc_name}")
    return {"status": "success", "message": "Document uploaded successfully", "url": full_url}


@router.post("/delete-plot-document")
def delete_plot_doc(doc_id: int = Form(...), db: Session = Depends(get_db)):
    doc = db.query(models.PlotDocument).filter(models.PlotDocument.id == doc_id).first()
    if doc:
        plot_id = doc.plot_id
        doc_name = doc.document_name
        db.delete(doc)
        db.commit()
        log_activity(db, plot_id, "Document Removed", f"Deleted: {doc_name}")
        return {"status": "success", "message": "Document removed"}
    return {"status": "error", "message": "Not found"}


# 🔴 5. COMMISSION & STAFF ASSIGNMENT ROUTES (WITH AUDIT) 🔴
@router.post("/update-commission-info")
def update_commission_information(
    plot_id: int = Form(...), booked_by: str = Form(None), commission_per_sqft: float = Form(None),
    commission_paid: float = Form(None), db: Session = Depends(get_db)
):
    plot = db.query(models.Plot).filter(models.Plot.id == plot_id).first()
    if not plot: raise HTTPException(status_code=404, detail="Plot not found")

    if booked_by is not None: plot.booked_by = booked_by
    if commission_per_sqft is not None: plot.commission_per_sqft = commission_per_sqft
    if commission_paid is not None: plot.commission_paid_amount = commission_paid

    sqft = plot.plot_size_sqft or 0.0
    rate = plot.commission_per_sqft or 0.0
    total = round(float(sqft) * float(rate), 2)
    paid = float(plot.commission_paid_amount or 0.0)
    
    plot.total_commission = total
    plot.commission_balance = max(0.0, total - paid)
    db.commit()
    log_activity(db, plot_id, "Commission Updated", f"Commission details updated for {plot.booked_by}")
    return {"status": "success", "message": "Commission updated"}


@router.post("/assign-staff")
def assign_staff_to_plot(
    plot_id: int = Form(...),
    staff_id: int = Form(...),
    db: Session = Depends(get_db)
):
    plot = db.query(models.Plot).filter(models.Plot.id == plot_id).first()
    if not plot:
        raise HTTPException(status_code=404, detail="Plot not found")
    
    plot.assigned_staff_id = staff_id
    db.commit()
    
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    log_activity(db, plot_id, "Staff Assigned", f"Assigned to {staff.name if staff else 'Staff'}")
    
    return {"status": "success", "message": "Staff assigned successfully"}


# 🔴 6. KYC UPDATE & UPLOAD ROUTE WITH AUDIT HISTORY 🔴
UPLOAD_DIR = "uploads/kyc"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_file(file: UploadFile):
    if not file or not file.filename:
        return None
    try:
        file_extension = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return f"http://localhost:8000/uploads/kyc/{file_name}"
    except Exception as e:
        return None

@router.post("/update-kyc-info")
async def update_kyc_info(
    plot_id: int = Form(...),
    client_id: int = Form(...),
    name: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    address: str = Form(None),
    pan: str = Form(None),
    aadhaar: str = Form(None),
    national_id: str = Form(None),
    pan_file: UploadFile = File(None),
    aadhaar_file: UploadFile = File(None),
    national_id_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        buyer = db.query(models.Client).filter(models.Client.id == client_id).first()
        if not buyer:
            return {"status": "error", "message": "Client not found"}

        if name: buyer.name = name
        if phone: buyer.contact_no = phone
        if email: buyer.email = email
        if address: buyer.address = address
        if pan: buyer.pan_card = pan
        if aadhaar: buyer.aadhaar_card = aadhaar 
        if national_id: buyer.national_id = national_id

        pan_url = await save_file(pan_file) if pan_file else None
        aadhaar_url = await save_file(aadhaar_file) if aadhaar_file else None
        national_id_url = await save_file(national_id_file) if national_id_file else None

        if pan_url: buyer.pan_doc_url = pan_url
        if aadhaar_url: buyer.aadhaar_doc_url = aadhaar_url
        if national_id_url: buyer.national_id_doc_url = national_id_url

        db.commit()
        log_activity(db, plot_id, "KYC Updated", f"Client ({buyer.name}) KYC details/documents were updated.")

        return {"status": "success", "message": "KYC details updated successfully"}
    
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}