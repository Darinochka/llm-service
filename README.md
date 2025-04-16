# LLM Service with Telegram Bot

A B2C service that provides access to an LLM model through a Telegram bot, with subscription-based access control and coin-based wallet system.

## Features

- Telegram bot interface for user interaction
- Subscription-based access control
- Coin-based wallet system (10 coins per minute of subscription)
- Background processing of LLM requests using Celery
- PostgreSQL database with SQLAlchemy ORM
- FastAPI backend with JWT authentication
- Admin interface for user management
- Docker and docker-compose setup

## Prerequisites

- Docker and docker-compose
- Python 3.11+
- PostgreSQL
- Redis
- vLLM server running with OpenAI-compatible API

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd llm-service
```

2. Create a `.env` file from the template:
```bash
cp .env.example .env
```

3. Update the `.env` file with your configuration:
- Set your Telegram bot token
- Configure database credentials
- Set JWT secret key
- Update vLLM API URL

4. Build and start the services:
```bash
docker-compose up --build
```

5. Run database migrations:
```bash
docker-compose exec api alembic upgrade head
```

## Architecture

### Components

1. **API Service (FastAPI)**
   - Handles HTTP requests
   - Manages user authentication
   - Processes subscriptions
   - Provides admin interface

2. **Telegram Bot**
   - User registration and authentication
   - Message handling
   - Subscription management
   - Direct interaction with LLM

3. **Celery Worker**
   - Background processing of LLM requests
   - Async task queue management

4. **Database (PostgreSQL)**
   - User management
   - Subscription tracking
   - Message history
   - Transaction records

5. **Redis**
   - Celery broker
   - Task queue backend

### Database Schema

- **users**: User information, authentication, and wallet balance
- **subscriptions**: Active user subscriptions
- **transactions**: Payment and coin transaction records
- **messages**: Chat history with LLM

## API Endpoints

### Public Endpoints

- `POST /message`: Submit a message to the LLM
- `GET /history`: Get message history
- `POST /subscribe`: Create a subscription (costs 10 coins per minute)
- `GET /me`: Get user info
- `GET /wallet`: Check wallet balance

### Admin Endpoints

- `GET /admin/users`: List all users
- `POST /admin/subscribe/{user_id}`: Force subscribe a user

## Telegram Bot Commands

- `/start`: Register/login (get 20 free coins)
- `/subscribe`: Show subscription status and payment info
- `/wallet`: Check your coin balance and add more coins

## Wallet System

- Each user starts with 20 free coins
- Subscription costs 10 coins per minute
- Users can add more coins through the Telegram bot
- Coin balance is displayed in the wallet interface
- Transaction history is maintained for all coin operations

## Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the API service:
```bash
uvicorn app.main:app --reload
```

3. Run the Telegram bot:
```bash
python app/run_bot.py
```

4. Run Celery worker:
```bash
celery -A app.worker worker --loglevel=info
```

5. Run Celery Flower (monitoring):
```bash
celery -A app.worker flower
```

## Monitoring

- Celery Flower: http://localhost:5555
- FastAPI docs: http://localhost:8000/docs

## License

MIT