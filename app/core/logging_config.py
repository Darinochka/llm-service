import logging
import logging.config
import os
from datetime import datetime

# Define logs directory path - use /tmp for Docker compatibility
LOGS_DIR = os.environ.get("LOGS_DIR", "/tmp/logs")

# Create logs directory if it doesn't exist
os.makedirs(LOGS_DIR, exist_ok=True)

# Define logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "detailed",
            "filename": os.path.join(LOGS_DIR, f"llm_service_{datetime.now().strftime('%Y%m%d')}.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": os.path.join(LOGS_DIR, f"llm_service_error_{datetime.now().strftime('%Y%m%d')}.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8",
        },
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": True,
        },
        "app": {  # Application logger
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "app.telegram_bot": {  # Telegram bot logger
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "app.tasks": {  # Tasks logger
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "sqlalchemy.engine": {  # SQLAlchemy logger
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Initialize logging configuration
logging.config.dictConfig(LOGGING_CONFIG) 