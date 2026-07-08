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
        logger.info("🚀 XAUUSD Signal Bot v3.0")
        logger.info("📊 Only monitoring: XAUUSD (Gold)")
        logger.info("=" * 60)
        
        try:
            Config.validate()
            logger.info("✅ Configuration validated")
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            sys.exit(1)
        
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.signal_generator = SignalGenerator()
        self.mt5 = MT5Connector()
        self.user_manager = UserManager(self.db)
        self.telegram = TelegramBot(self.db, self.signal_generator)
        
        self.running = False
        self.signals_sent = 0
        
        logger.info(f"👥 Max Users: {Config.MAX_USERS}")
        logger.info(f"⏰ Timezone: {Config.TIMEZONE}")
    
    def start(self):
        if self.running:
            return
        
        logger.info("🟢 Starting bot...")
        self.running = True
        
        self.mt5.connect()
        
        # Start Telegram bot
        telegram_thread = threading.Thread(target=self.telegram.start, daemon=True)
        telegram_thread.start()
        time.sleep(3)  # Wait for Telegram to start
        
        # Start signal loop
        signal_thread = threading.Thread(target=self._signal_loop, daemon=True)
        signal_thread.start()
        
        # Start result checker
        result_thread = threading.Thread(target=self._result_checker_loop, daemon=True)
        result_thread.start()
        
        logger.info("✅ Bot started!")
        self._print_status()
    
    def stop(self):
        logger.info("🔴 Stopping bot...")
        self.running = False
        self.mt5.disconnect()
        self.telegram.stop()
        logger.info("✅ Bot stopped")
    
    def _signal_loop(self):
        """Continuous XAUUSD signals - EVERY 10 SECONDS"""
        logger.info("🔄 XAUUSD Signal loop started - checking every 10 seconds...")
        
        while self.running:
            try:
                symbol = 'XAUUSD'
                
                # Get market data
                df = self.mt5.get_market_data(symbol, Config.TIMEFRAME, 100)
                
                if df is not None and len(df) >= 50:
                    # Generate signal
                    signal = self.signal_generator.generate_signal(df, symbol)
                    
                    if signal and signal['direction'] != 'NEUTRAL':
                        if signal['confidence'] >= Config.MIN_CONFIDENCE:
                            logger.info(f"🎯 XAUUSD Signal: {signal['direction']} ({signal['confidence']:.1f}%)")
                            signal_id = self.telegram.send_signal(signal, Config.SIGNAL_TIMES)
                            if signal_id:
                                self.signals_sent += 1
                                logger.info(f"✅ XAUUSD Signal sent! (Total: {self.signals_sent})")
                
                # Check every 10 seconds for FAST signals
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in signal loop: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(5)
    
    def _result_checker_loop(self):
        """Check for expired signals"""
        logger.info("🔄 Result checker loop started")
        
        while self.running:
            try:
                self.telegram.check_pending_results()
                time.sleep(15)
            except Exception as e:
                logger.error(f"Error in result checker: {e}")
                time.sleep(15)
    
    def _print_status(self):
        user_count = self.user_manager.get_user_count()
        stats = self.db.get_statistics()
        current_time = Config.get_current_time().strftime("%H:%M:%S")
        
        status = f"""
╔═══════════════════════════════════════════════════════════╗
║              XAUUSD SIGNAL BOT - RUNNING                ║
╠═══════════════════════════════════════════════════════════╣
║ ✅ Status: Online                        Time: {current_time}    ║
║ 📊 Symbol: XAUUSD (Gold)                                  ║
║ 👥 Users: {user_count}/{Config.MAX_USERS:<2}                                                ║
║ 📈 Signals Sent: {self.signals_sent}                                                ║
║ ⏰ Timezone: Erbil/Iraq (UTC+3)                                        ║
║ 🔗 Invite: @sombre_signal_bot                                        ║
╚═══════════════════════════════════════════════════════════╝
        """
        logger.info(status)

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
        logger.error(f"❌ Fatal error: {e}")
        if bot:
            bot.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
