import os
from dotenv import load_dotenv
import logging

# Load environment variables
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
    SYMBOLS = [x.strip() for x in os.getenv('SYMBOLS', 'USDJPY,USDCHF,USDBRL,JODCNY').split(',')]
    
    # Invite System
    INVITE_CODE = os.getenv('INVITE_CODE', 'MYBOT2026')
    INVITE_LINK = os.getenv('INVITE_LINK', 'https://t.me/YourBotUsername?start=invite_MYBOT2026')
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/signals.db')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
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