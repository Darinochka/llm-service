from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, UTC
from typing import List
from pydantic import BaseModel

from app.db.session import get_db
from app.models import models
from app.schemas import user, subscription, message
from app.core.config import settings
from app.tasks import process_llm_request
from jose import JWTError, jwt

app = FastAPI(title="LLM Service API")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class TokenRequest(BaseModel):
    telegram_id: str

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

@app.post("/token")
async def get_token(token_request: TokenRequest, db: Session = Depends(get_db)):
    # Check if user exists
    user = db.query(models.User).filter(models.User.telegram_id == token_request.telegram_id).first()
    
    if not user:
        # Create new user
        user = models.User(
            telegram_id=token_request.telegram_id,
            role=models.UserRole.USER
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create access token
    access_token = create_access_token({"sub": token_request.telegram_id})
    return {"access_token": access_token, "token_type": "bearer"}

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
        models.Subscription.end_date > datetime.now(UTC)
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

    process_llm_request(db_message.id)
    db.refresh(db_message)

    return message.MessageResponse(response=db_message.response)

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
        models.Subscription.end_date > datetime.now(UTC)
    ).first()
    
    if active_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active subscription already exists"
        )

    # Calculate subscription cost (10 coins per minute)
    subscription_duration_minutes = settings.SUBSCRIPTION_DURATION_MIN
    subscription_cost = subscription_duration_minutes * settings.SUBSCRIPTION_PRICE_RUB

    # Check if user has enough coins
    if current_user.wallet < subscription_cost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not enough coins. Required: {subscription_cost}, Available: {current_user.wallet}"
        )

    # Create subscription
    start_date = datetime.now(UTC)
    end_date = start_date + timedelta(minutes=settings.SUBSCRIPTION_DURATION_MIN)
    
    subscription = models.Subscription(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    db.add(subscription)

    # Deduct coins from wallet
    current_user.wallet -= subscription_cost

    # Create transaction
    transaction = models.Transaction(
        user_id=current_user.id,
        amount=subscription_cost,
        type=models.TransactionType.SUBSCRIPTION
    )
    db.add(transaction)
    
    db.commit()
    return {"message": "Subscription created successfully", "coins_spent": subscription_cost, "remaining_coins": current_user.wallet}

@app.get("/wallet", response_model=dict)
async def get_wallet_balance(current_user: models.User = Depends(get_current_user)):
    return {
        "balance": current_user.wallet,
        "subscription_cost_per_minute": 10
    }

@app.get("/me", response_model=user.User)
async def get_user_info(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.post("/add_coins")
async def add_coins(
    coins_request: user.AddCoinsRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Add coins to user's wallet
    current_user.wallet += coins_request.amount
    
    # Create transaction record
    transaction = models.Transaction(
        user_id=current_user.id,
        amount=coins_request.amount,
        type=models.TransactionType.ADD_COINS
    )
    db.add(transaction)
    db.commit()
    
    return {"message": f"{coins_request.amount} coins added successfully", "new_balance": current_user.wallet}

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

    start_date = datetime.now(UTC)
    end_date = start_date + timedelta(minutes=settings.SUBSCRIPTION_DURATION_MIN)
    
    subscription = models.Subscription(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    db.add(subscription)
    db.commit()
    
    return {"message": f"Subscription created for user {user_id}"} 