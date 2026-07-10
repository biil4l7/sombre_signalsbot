#!/usr/bin/env python
import os
import sys
import time
import signal
import threading
from datetime import datetime

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
        logger.info("🚀 XAUUSD Signal Bot - FAST MODE")
        logger.info("📊 Signals every 5-10 seconds")
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
        logger.info(f"🎯 Min Confidence: {Config.MIN_CONFIDENCE}%")
    
    def start(self):
        if self.running:
            return
        
        logger.info("🟢 Starting...")
        self.running = True
        
        self.mt5.connect()
        
        # Start Telegram
        t = threading.Thread(target=self.telegram.start, daemon=True)
        t.start()
        time.sleep(3)
        
        # Start signal loop (FAST)
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
        """FAST signal loop - every 5 seconds"""
        logger.info("🔄 Signal loop - checking EVERY 5 SECONDS...")
        
        while self.running:
            try:
                # Get fresh data
                df = self.mt5.get_market_data('XAUUSD', Config.TIMEFRAME, 100)
                
                if df is not None and len(df) >= 50:
                    # Generate signal
                    signal = self.signal_generator.generate_signal(df, 'XAUUSD')
                    
                    if signal and signal['direction'] != 'NEUTRAL':
                        if signal['confidence'] >= Config.MIN_CONFIDENCE:
                            logger.info(f"🎯 XAUUSD {signal['direction']} ({signal['confidence']:.1f}%)")
                            signal_id = self.telegram.send_signal(signal, Config.SIGNAL_TIMES)
                            if signal_id:
                                self.signals_sent += 1
                                logger.info(f"✅ Sent! (Total: {self.signals_sent})")
                
                # Check every 5 seconds for FAST signals
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(2)
    
    def _result_loop(self):
        """Check results every 10 seconds"""
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
║              XAUUSD BOT - FAST MODE                     ║
╠═══════════════════════════════════════════════════════════╣
║ 📊 Symbol: XAUUSD (Gold)                                 ║
║ 👥 Users: {user_count}/{Config.MAX_USERS}                                                ║
║ 📈 Signals Sent: {self.signals_sent}                                                ║
║ 🏆 Win Rate: {stats['win_rate']:.1f}%                                                 ║
║ ⏱️ Check Interval: 5 seconds                               ║
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
        logger.info("👋 Stopped")
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
