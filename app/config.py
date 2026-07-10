import os
from dotenv import load_dotenv
import pytz

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID', '0'))
    MAX_USERS = int(os.getenv('MAX_USERS', '6'))
    MIN_CONFIDENCE = 55
    SIGNAL_TIMES = [3, 5]
    TIMEFRAME = 'M1'
    SYMBOLS = ['XAUUSD']
    INVITE_CODE = os.getenv('INVITE_CODE', 'SOMMER2026')
    INVITE_LINK = os.getenv('INVITE_LINK', 'https://t.me/sombre_signal_bot?start=invite_SOMMER2026')
    DATABASE_PATH = os.getenv('DATABASE_PATH', '/app/data/signals.db')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    TIMEZONE = pytz.timezone('Asia/Baghdad')
    
    @classmethod
    def get_current_time(cls):
        from datetime import datetime
        return datetime.now(cls.TIMEZONE)
    
    @classmethod
    def validate(cls):
        errors = []
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN is required")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is required")
        if errors:
            raise ValueError(f"Config errors: {', '.join(errors)}")
        return True
