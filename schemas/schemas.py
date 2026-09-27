from pydantic import BaseModel
from typing import Optional
from datetime import date

class ClientCreate(BaseModel):
    project_id: int
    plot_no: str
    plot_size_sqft: float
    rate: float
    buyer_name: str
    buyer_phone: str
    buyer_email: Optional[str] = None
    booking_date: date
    booking_amount: float
    commission_per_sqft: float
    commission_paid: float
    booked_by: str

class PaymentCreate(BaseModel):
    plot_id: int
    payment_date: date
    amount: float
    cheque_no: Optional[str] = None
    cheque_date: Optional[date] = None
    bank_name: Optional[str] = None
    drawn_on: Optional[str] = None
    received_date: date
    booked_by: str
    remark: Optional[str] = None