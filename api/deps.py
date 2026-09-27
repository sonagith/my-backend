# api/deps.py
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from core.security import verify_token
from db.database import get_db
from db import models

# Yeh function route ko secure karega
def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing or invalid format (Use 'Bearer <token>')"
        )
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    
    if payload is None or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid"
        )
    
    # Token me email chupi hoti hai, usko Database me dhundho
    email = payload.get("sub")
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found in Database")
        
    return user