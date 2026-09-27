# api/routes/auth.py
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.security import create_access_token, verify_password
from db.database import get_db
from db import models

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # 1. Database mein User dhundho
    user = db.query(models.User).filter(models.User.email == request.email).first()
    
    # 2. Check karo agar user hai aur password match ho raha hai
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid email or password"
        )
    
    # 3. Agar sab sahi hai, token generate karo
    token = create_access_token(data={"sub": user.email})
    return {
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer"
    }