from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from app.db.session import get_db
from app.models import models
from app.schemas import user, subscription, message
from app.core.config import settings
from app.tasks import process_llm_request
from jose import JWTError, jwt

app = FastAPI(title="LLM Service API")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        telegram_id: str = payload.get("sub")
        if telegram_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/message", response_model=message.MessageResponse)
async def create_message(
    message_in: message.MessageCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check subscription
    active_subscription = db.query(models.Subscription).filter(
        models.Subscription.user_id == current_user.id,
        models.Subscription.end_date > datetime.utcnow()
    ).first()
    
    if not active_subscription:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required"
        )

    # Create message
    db_message = models.Message(
        user_id=current_user.id,
        content=message_in.content,
        response="Processing..."
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)

    # Process message asynchronously
    process_llm_request.delay(db_message.id)

    return message.MessageResponse(response="Processing your request...")

@app.get("/history", response_model=List[message.Message])
async def get_message_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    messages = db.query(models.Message).filter(
        models.Message.user_id == current_user.id
    ).order_by(models.Message.created_at.desc()).all()
    return messages

@app.post("/subscribe")
async def create_subscription(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if user already has an active subscription
    active_subscription = db.query(models.Subscription).filter(
        models.Subscription.user_id == current_user.id,
        models.Subscription.end_date > datetime.utcnow()
    ).first()
    
    if active_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active subscription already exists"
        )

    # Create subscription
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
    
    subscription = models.Subscription(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    db.add(subscription)

    # Create transaction
    transaction = models.Transaction(
        user_id=current_user.id,
        amount=settings.SUBSCRIPTION_PRICE_RUB,
        type=models.TransactionType.SUBSCRIPTION
    )
    db.add(transaction)
    
    db.commit()
    return {"message": "Subscription created successfully"}

@app.get("/me", response_model=user.User)
async def get_user_info(current_user: models.User = Depends(get_current_user)):
    return current_user

# Admin endpoints
@app.get("/admin/users", response_model=List[user.User])
async def list_users(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    users = db.query(models.User).all()
    return users

@app.post("/admin/subscribe/{user_id}")
async def admin_subscribe_user(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
    
    subscription = models.Subscription(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    db.add(subscription)
    db.commit()
    
    return {"message": f"Subscription created for user {user_id}"} 