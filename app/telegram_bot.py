from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import models
from app.tasks import process_llm_request

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(models.User).filter(
            models.User.telegram_id == str(message.from_user.id)
        ).first()
        
        if not user:
            # Create new user
            user = models.User(
                telegram_id=str(message.from_user.id),
                role=models.UserRole.USER
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            await message.answer(
                "Welcome! You've been registered. Use /subscribe to get access to the LLM service."
            )
        else:
            await message.answer(
                "Welcome back! You can send any message to interact with the LLM."
            )
    finally:
        db.close()

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.telegram_id == str(message.from_user.id)
        ).first()
        
        if not user:
            await message.answer("Please use /start first to register.")
            return

        # Check if user already has an active subscription
        active_subscription = db.query(models.Subscription).filter(
            models.Subscription.user_id == user.id,
            models.Subscription.end_date > datetime.utcnow()
        ).first()
        
        if active_subscription:
            await message.answer(
                f"You already have an active subscription until {active_subscription.end_date.strftime('%Y-%m-%d')}."
            )
            return

        # Create subscription
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
        
        subscription = models.Subscription(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date
        )
        db.add(subscription)

        # Create transaction
        transaction = models.Transaction(
            user_id=user.id,
            amount=settings.SUBSCRIPTION_PRICE_RUB,
            type=models.TransactionType.SUBSCRIPTION
        )
        db.add(transaction)
        
        db.commit()
        
        await message.answer(
            f"Subscription created successfully! You now have access until {end_date.strftime('%Y-%m-%d')}."
        )
    finally:
        db.close()

@dp.message()
async def handle_message(message: Message):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.telegram_id == str(message.from_user.id)
        ).first()
        
        if not user:
            await message.answer("Please use /start first to register.")
            return

        # Check subscription
        active_subscription = db.query(models.Subscription).filter(
            models.Subscription.user_id == user.id,
            models.Subscription.end_date > datetime.utcnow()
        ).first()
        
        if not active_subscription:
            await message.answer(
                "You need an active subscription to use the service. Use /subscribe to get access."
            )
            return

        # Create message record
        db_message = models.Message(
            user_id=user.id,
            content=message.text,
            response="Processing..."
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)

        # Send processing message
        processing_msg = await message.answer("Processing your request...")

        # Process message asynchronously
        process_llm_request.delay(db_message.id)

        # Wait for response (in a real implementation, you'd want to use a proper async queue)
        while db_message.response == "Processing...":
            await asyncio.sleep(1)
            db.refresh(db_message)

        # Update the processing message with the actual response
        await processing_msg.edit_text(db_message.response)
    finally:
        db.close()

async def start_bot():
    await dp.start_polling(bot) 