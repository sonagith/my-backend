from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from api.deps import get_db, get_current_user
from db import models
from datetime import date
import shutil
import uuid
import os

router = APIRouter()

@router.post("/")
async def add_payment(
    plot_id: int = Form(...),
    payment_date: date = Form(...),
    amount: float = Form(...),
    cheque_no: str = Form(None),
    cheque_date: date = Form(None),
    bank_name: str = Form(None),
    drawn_on: str = Form(None),
    received_date: date = Form(...),
    booked_by: str = Form(None),
    remark: str = Form(None),
    receipt_image: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    file_url = None
    if receipt_image and receipt_image.filename:
        ext = receipt_image.filename.split('.')[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = f"uploads/receipts/{filename}"
        
        os.makedirs("uploads/receipts", exist_ok=True)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(receipt_image.file, buffer)
            
        # 🔴 CHANGED: Sirf relative path
        file_url = f"/{filepath}" 

    new_payment = models.Payment(
        plot_id=plot_id,
        date=payment_date,
        amount=amount,
        drawn_on=drawn_on or bank_name,
        cheque_no=cheque_no,
        ch_date=cheque_date,
        remarks=remark,
        receipt_url=file_url 
    )
    db.add(new_payment)
    db.commit()
    return {"status": "success", "message": "Payment & Receipt Uploaded!"}