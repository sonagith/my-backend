from sqlalchemy.orm import Session
from db import models
from schemas import schemas

def add_new_payment(db: Session, payment_data: schemas.PaymentCreate):
    new_payment = models.Payment(
        plot_id=payment_data.plot_id,
        date=payment_data.payment_date,
        amount=payment_data.amount,
        drawn_on=payment_data.drawn_on,
        cheque_no=payment_data.cheque_no,
        ch_date=payment_data.cheque_date,
        remarks=payment_data.remark
    )
    db.add(new_payment)
    db.commit()
    return new_payment