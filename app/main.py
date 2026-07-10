#!/usr/bin/env python
import os
import sys
import time
import signal
import threading
from datetime import datetime

# Ensure /app/data exists for database
os.makedirs('/app/data', exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Config
from app.utils.logger import logger
from app.database.db_manager import DatabaseManager
from app.modules.signal_generator import SignalGenerator
from app.modules.mt5_connector import MT5Connector
from app.modules.telegram_bot import TelegramBot
from app.modules.user_manager import UserManager

class SignalBot:
    def __init__(self):
        logger.info("=" * 60)
        logger.info("🚀 XAUUSD Signal Bot - FINAL")
        logger.info("📊 Forced signals every 10 seconds")
        logger.info("=" * 60)
        
        try:
            Config.validate()
            logger.info("✅ Config OK")
        except ValueError as e:
            logger.error(f"❌ Config error: {e}")
            sys.exit(1)
        
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.signal_generator = SignalGenerator()
        self.mt5 = MT5Connector()
        self.user_manager = UserManager(self.db)
        self.telegram = TelegramBot(self.db, self.signal_generator)
        
        self.running = False
        self.signals_sent = 0
        
        logger.info(f"📊 XAUUSD Only")
        logger.info(f"👥 Max Users: {Config.MAX_USERS}")
        logger.info(f"🗄️ Database: {Config.DATABASE_PATH}")
    
    def start(self):
        if self.running:
            return
        logger.info("🟢 Starting...")
        self.running = True
        self.mt5.connect()
        
        # Start Telegram bot
        t = threading.Thread(target=self.telegram.start, daemon=True)
        t.start()
        time.sleep(3)  # Give Telegram time to initialize
        
        # Start signal loop (every 10 seconds)
        t2 = threading.Thread(target=self._signal_loop, daemon=True)
        t2.start()
        
        # Start result checker
        t3 = threading.Thread(target=self._result_loop, daemon=True)
        t3.start()
        
        logger.info("✅ Bot started!")
        self._print_status()
    
    def stop(self):
        logger.info("🔴 Stopping...")
        self.running = False
        self.mt5.disconnect()
        self.telegram.stop()
        logger.info("✅ Stopped")
    
    def _signal_loop(self):
        """Force signals every 10 seconds"""
        logger.info("🔄 Signal loop - sending forced signal every 10 seconds...")
        directions = ['CALL', 'PUT']
        idx = 0
        while self.running:
            try:
                direction = directions[idx % 2]
                idx += 1
                # Create a dummy signal with realistic data
                signal = {
                    'symbol': 'XAUUSD',
                    'direction': direction,
                    'confidence': 65.0 + (idx % 5) * 2,  # 65-75%
                    'price': 2350.0 + (idx * 10),        # rising price
                    'indicators': ['RSI Oversold' if direction == 'CALL' else 'RSI Overbought',
                                   'MA Bullish' if direction == 'CALL' else 'MA Bearish'],
                    'score': 30 if direction == 'CALL' else -30
                }
                logger.info(f"🎯 FORCED XAUUSD {direction} (Confidence: {signal['confidence']:.1f}%)")
                signal_id = self.telegram.send_signal(signal, Config.SIGNAL_TIMES)
                if signal_id:
                    self.signals_sent += 1
                    logger.info(f"✅ Sent! (Total: {self.signals_sent})")
                time.sleep(10)  # Wait 10 seconds before next signal
            except Exception as e:
                logger.error(f"Error in signal loop: {e}")
                time.sleep(5)
    
    def _result_loop(self):
        logger.info("🔄 Result checker started")
        while self.running:
            try:
                self.telegram.check_pending_results()
                time.sleep(10)
            except Exception as e:
                logger.error(f"Result error: {e}")
                time.sleep(10)
    
    def _print_status(self):
        user_count = self.user_manager.get_user_count()
        stats = self.db.get_statistics()
        logger.info(f"""
╔═══════════════════════════════════════════════════════════╗
║              XAUUSD BOT - FINAL                         ║
╠═══════════════════════════════════════════════════════════╣
║ 📊 Symbol: XAUUSD (Gold)                                 ║
║ 👥 Users: {user_count}/{Config.MAX_USERS}                                                ║
║ 📈 Signals Sent: {self.signals_sent}                                                ║
║ 🏆 Win Rate: {stats['win_rate']:.1f}%                                                 ║
║ ⏱️ Interval: 10 seconds                                  ║
║ 🗄️ Database: {Config.DATABASE_PATH}                    ║
╚═══════════════════════════════════════════════════════════╝
        """)

def signal_handler(sig, frame):
    logger.info("\n⚠️ Shutting down...")
    if bot:
        bot.stop()
    sys.exit(0)

bot = None

def main():
    global bot
    try:
        bot = SignalBot()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        bot.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("👋 Stopped by user")
        if bot:
            bot.stop()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal: {e}")
        if bot:
            bot.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
