from pydantic import BaseModel
from datetime import datetime

class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    content: str

class Message(MessageBase):
    id: int
    user_id: int
    response: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    response: str 