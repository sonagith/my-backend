from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.deps import get_db
from schemas import schemas
from services import client_service
from api.deps import get_db, get_current_user 
router = APIRouter()

@router.post("/")
def add_client(client_data: schemas.ClientCreate, db: Session = Depends(get_db)):
    plot = client_service.create_client_and_plot(db, client_data)
    return {"status": "success", "message": "Client added successfully!", "plot_id": plot.id}


@router.post("/")
def add_client(
    client_data: schemas.ClientCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user) # Bina token ye route FAIL ho jayega!
):
    plot = client_service.create_client_and_plot(db, client_data)
    return {"status": "success", "message": "Client added successfully!", "plot_id": plot.id}