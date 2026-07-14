#!/usr/bin/env python
import os
import sys
import asyncio
import time
import signal
from datetime import datetime, timedelta

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

# Global references
bot_instance = None

class SignalBot:
    def __init__(self):
        logger.info("=" * 60)
        logger.info("🚀 XAUUSD Signal Bot - FORCED TEST MODE")
        logger.info("📊 Forced signals every 30 seconds")
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
        
        # Pass MT5 connector to telegram bot for price lookup
        self.telegram.set_mt5_connector(self.mt5)
        
        self.running = False
        self.signals_sent = 0
        
        logger.info(f"📊 XAUUSD Only")
        logger.info(f"👥 Max Users: {Config.MAX_USERS}")
        logger.info(f"🗄️ Database: {Config.DATABASE_PATH}")
    
    async def start(self):
        logger.info("🟢 Starting bot...")
        self.running = True
        self.mt5.connect()
        
        # Start Telegram bot
        await self.telegram.start()
        
        # Start signal generation loop (FORCED)
        asyncio.create_task(self._signal_loop())
        
        # Start result checker
        asyncio.create_task(self._result_loop())
        
        logger.info("✅ Bot started!")
        self._print_status()
    
    async def stop(self):
        logger.info("🔴 Stopping...")
        self.running = False
        self.mt5.disconnect()
        await self.telegram.stop()
        logger.info("✅ Stopped")
    
    async def _signal_loop(self):
        """FORCED signals every 30 seconds - for testing Telegram delivery"""
        logger.info("🔄 FORCED signal loop - sending every 30 seconds...")
        directions = ['CALL', 'PUT']
        idx = 0
        
        while self.running:
            try:
                # Wait until no pending signals (so results are sent first)
                while len(self.telegram.pending_signals) > 0 and self.running:
                    await asyncio.sleep(5)
                if not self.running:
                    break
                
                direction = directions[idx % 2]
                idx += 1
                
                # Create a dummy signal with realistic data
                signal = {
                    'symbol': 'XAUUSD',
                    'direction': direction,
                    'confidence': 65.0 + (idx % 5) * 2,
                    'price': 2350.0 + (idx * 10),
                    'indicators': ['RSI Oversold' if direction == 'CALL' else 'RSI Overbought',
                                   'MA Bullish' if direction == 'CALL' else 'MA Bearish'],
                }
                
                logger.info(f"🎯 FORCED XAUUSD {direction} (Confidence: {signal['confidence']:.1f}%)")
                signal_id = await self.telegram.send_signal(signal, Config.SIGNAL_TIMES)
                if signal_id:
                    self.signals_sent += 1
                    logger.info(f"✅ Sent! (Total: {self.signals_sent})")
                
                await asyncio.sleep(30)  # Wait 30 seconds before next forced signal
                
            except Exception as e:
                logger.error(f"Error in signal loop: {e}")
                await asyncio.sleep(30)
    
    async def _result_loop(self):
        logger.info("🔄 Result checker started")
        while self.running:
            try:
                await self.telegram.check_pending_results()
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Result error: {e}")
                await asyncio.sleep(10)
    
    def _print_status(self):
        user_count = self.user_manager.get_user_count()
        stats = self.db.get_statistics()
        logger.info(f"""
╔═══════════════════════════════════════════════════════════╗
║              XAUUSD BOT - FORCED TEST                   ║
╠═══════════════════════════════════════════════════════════╣
║ 📊 Symbol: XAUUSD (Gold) - FORCED SIGNALS               ║
║ 👥 Users: {user_count}/{Config.MAX_USERS}                                                ║
║ 📈 Signals Sent: {self.signals_sent}                                                ║
║ 🏆 Win Rate: {stats['win_rate']:.1f}%                                                 ║
║ ⏱️ Interval: 30 seconds (forced)                        ║
╚═══════════════════════════════════════════════════════════╝
        """)

async def main():
    global bot_instance
    bot_instance = SignalBot()
    await bot_instance.start()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await bot_instance.stop()

def signal_handler(sig, frame):
    logger.info("\n⚠️ Shutting down...")
    if bot_instance:
        asyncio.create_task(bot_instance.stop())
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    asyncio.run(main())
