from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.models import UserRole

class UserBase(BaseModel):
    telegram_id: str
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    wallet: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserInDB(User):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    telegram_id: Optional[str] = None

class AddCoinsRequest(BaseModel):
    amount: int 