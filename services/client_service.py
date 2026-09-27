from sqlalchemy.orm import Session
from db import models
from schemas import schemas

def create_client_and_plot(db: Session, client_data: schemas.ClientCreate):
    # 1. Create or Find Client
    client = db.query(models.Client).filter(models.Client.contact_no == client_data.buyer_phone).first()
    if not client:
        client = models.Client(name=client_data.buyer_name, contact_no=client_data.buyer_phone)
        db.add(client)
        db.commit()
        db.refresh(client)
    
    # 2. Create Plot
    total_value = client_data.plot_size_sqft * client_data.rate
    new_plot = models.Plot(
        plot_no=client_data.plot_no,
        project_id=client_data.project_id,
        client_id=client.id,
        plot_size_sqft=client_data.plot_size_sqft,
        rate=client_data.rate,
        plot_value=total_value,
        sale_date=client_data.booking_date,
        booked_by=client_data.booked_by,
        commission=client_data.commission_per_sqft
    )
    db.add(new_plot)
    db.commit()
    db.refresh(new_plot)

    # 3. Add Initial Payment (Booking Amount)
    payment = models.Payment(
        plot_id=new_plot.id,
        date=client_data.booking_date,
        amount=client_data.booking_amount,
        drawn_on="Cash",
        remarks="Booking Amount"
    )
    db.add(payment)
    db.commit()

    return new_plot