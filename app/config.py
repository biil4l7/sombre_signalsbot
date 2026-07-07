import os
from dotenv import load_dotenv
import pytz

load_dotenv()

class Config:
    """Configuration management class"""
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID', '0'))
    
    # Bot Settings
    MAX_USERS = int(os.getenv('MAX_USERS', '6'))
    MIN_CONFIDENCE = int(os.getenv('MIN_CONFIDENCE', '60'))
    SIGNAL_TIMES = [int(x.strip()) for x in os.getenv('SIGNAL_TIMES', '3,5').split(',')]
    TIMEFRAME = os.getenv('TIMEFRAME', 'M1')
    SYMBOLS = [x.strip() for x in os.getenv('SYMBOLS', 'USDJPY,USDCHF,USDBRL,JODCNY,XAUUSD').split(',')]
    # Invite System
    INVITE_CODE = os.getenv('INVITE_CODE', 'SOMMER2026')
    INVITE_LINK = os.getenv('INVITE_LINK', 'https://t.me/sombre_signal_bot?start=invite_SOMMER2026')
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/signals.db')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Timezone - Erbil/Iraq (UTC+3)
    TIMEZONE = pytz.timezone('Asia/Baghdad')  # Iraq timezone
    
    @classmethod
    def get_current_time(cls):
        """Get current time in Erbil/Iraq timezone"""
        from datetime import datetime
        return datetime.now(cls.TIMEZONE)
    
    @classmethod
    def validate(cls):
        """Validate required configurations"""
        errors = []
        
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN is required")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID is required")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True
