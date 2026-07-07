#!/usr/bin/env python
"""
Signal Bot - Railway Edition
Main entry point for the bot
"""

import os
import sys
import time
import signal
import asyncio
import threading
from datetime import datetime

# Add app directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Config
from app.utils.logger import logger
from app.database.db_manager import DatabaseManager
from app.modules.signal_generator import SignalGenerator
from app.modules.mt5_connector import MT5Connector
from app.modules.telegram_bot import TelegramBot
from app.modules.user_manager import UserManager

class SignalBot:
    """Main Signal Bot class with Auto-Join Invite System"""
    
    def __init__(self):
        """Initialize bot components"""
        logger.info("=" * 60)
        logger.info("🚀 Signal Bot Pro - Railway Edition v3.0")
        logger.info("✨ Auto-Join Invite System Enabled")
        logger.info("=" * 60)
        
        # Validate configuration
        try:
            Config.validate()
            logger.info("✅ Configuration validated successfully")
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            sys.exit(1)
        
        # Initialize components
        self.db = DatabaseManager(Config.DATABASE_PATH)
        self.signal_generator = SignalGenerator()
        self.mt5 = MT5Connector()
        self.user_manager = UserManager(self.db)
        
        # Initialize telegram bot
        self.telegram = TelegramBot(self.db, self.signal_generator)
        
        # Bot state
        self.running = False
        self.signal_loop_thread = None
        
        # Stats
        self.last_check_time = None
        self.signals_sent = 0
        
        logger.info("✅ Bot components initialized successfully")
        logger.info(f"📊 Monitoring symbols: {', '.join(Config.SYMBOLS)}")
        logger.info(f"👥 Max users: {Config.MAX_USERS}")
        logger.info(f"⏰ Signal times: {Config.SIGNAL_TIMES} minutes before trade")
        logger.info(f"🎯 Min confidence: {Config.MIN_CONFIDENCE}%")
        logger.info(f"🔗 Invite Code: {Config.INVITE_CODE}")
        logger.info(f"🔗 Invite Link: {Config.INVITE_LINK}")
    
    def start(self):
        """Start the bot"""
        if self.running:
            logger.warning("Bot is already running")
            return
        
        logger.info("🟢 Starting Signal Bot...")
        self.running = True
        
        # Connect to MT5
        if not self.mt5.connect():
            logger.error("❌ Failed to connect to MT5")
            self.running = False
            return
        
        # Start Telegram bot in a separate thread
        telegram_thread = threading.Thread(target=self.telegram.start, daemon=True)
        telegram_thread.start()
        
        # Start signal generation loop
        self.signal_loop_thread = threading.Thread(target=self._signal_loop, daemon=True)
        self.signal_loop_thread.start()
        
        logger.info("✅ Bot started successfully!")
        self._print_status()
    
    def stop(self):
        """Stop the bot"""
        logger.info("🔴 Stopping Signal Bot...")
        self.running = False
        
        # Stop MT5
        self.mt5.disconnect()
        
        # Stop Telegram
        self.telegram.stop()
        
        # Wait for threads to finish
        if self.signal_loop_thread and self.signal_loop_thread.is_alive():
            self.signal_loop_thread.join(timeout=5)
        
        logger.info("✅ Bot stopped successfully")
    
    def _signal_loop(self):
        """Main signal generation loop"""
        logger.info("🔄 Signal generation loop started")
        
        while self.running:
            try:
                # Check for signals on each symbol
                for symbol in Config.SYMBOLS:
                    if not self.running:
                        break
                    
                    logger.debug(f"Checking {symbol}...")
                    
                    # Get market data
                    df = self.mt5.get_market_data(symbol, Config.TIMEFRAME, 100)
                    
                    if df is None or len(df) < 50:
                        logger.warning(f"⚠️ Insufficient data for {symbol}")
                        continue
                    
                    # Generate signal
                    signal = self.signal_generator.generate_signal(df, symbol)
                    
                    if signal and signal['direction'] != 'NEUTRAL':
                        # Check confidence
                        if signal['confidence'] >= Config.MIN_CONFIDENCE:
                            logger.info(f"🎯 Signal found: {symbol} - {signal['direction']} "
                                      f"(Confidence: {signal['confidence']:.1f}%)")
                            
                            # Send to Telegram
                            signal_id = self.telegram.send_signal(signal, Config.SIGNAL_TIMES)
                            
                            if signal_id:
                                self.signals_sent += 1
                                logger.info(f"✅ Signal sent! (Total: {self.signals_sent})")
                            
                            # Wait a bit before checking same symbol again
                            time.sleep(10)
                        else:
                            logger.debug(f"Signal confidence too low: {signal['confidence']:.1f}%")
                
                # Update last check time
                self.last_check_time = datetime.now()
                
                # Sleep before next check
                time.sleep(60)  # Check every 60 seconds
                
            except Exception as e:
                logger.error(f"Error in signal loop: {e}")
                time.sleep(30)  # Wait before retrying
    
    def _print_status(self):
        """Print bot status"""
        users = self.user_manager.get_users()
        user_list = "\n".join([f"  • {u['first_name']} (@{u['username']})" for u in users])
        
        status = f"""
╔═══════════════════════════════════════════════════════════╗
║                   BOT STATUS - v3.0                      ║
╠═══════════════════════════════════════════════════════════╣
║ ✅ Status: Running                                       ║
║ 📊 Symbols: {', '.join(Config.SYMBOLS):<40} ║
║ 👥 Users: {self.user_manager.get_user_count()}/{Config.MAX_USERS:<2}                                                ║
║ 🎯 Confidence: {Config.MIN_CONFIDENCE}%                                                ║
║ ⏰ Signal Times: {', '.join(map(str, Config.SIGNAL_TIMES))} minutes                              ║
║ 📈 Signals Sent: {self.signals_sent}                                                ║
║ 🔗 Invite Link: {Config.INVITE_LINK:<45} ║
║                                                                               ║
║ 👥 Active Users:                                                             ║
{user_list if user_list else '  • No users yet'}
║                                                                               ║
║ 💡 New users can join with: /invite                                           ║
╚═══════════════════════════════════════════════════════════╝
        """
        logger.info(status)
    
    def generate_invite(self):
        """Generate a new invite link"""
        invite_link, message = self.user_manager.generate_invite(
            self.telegram.bot_username
        )
        
        if invite_link:
            logger.info(f"New invite link generated: {invite_link}")
            return invite_link
        else:
            logger.error(f"Failed to generate invite: {message}")
            return None
    
    def test_signal(self):
        """Generate a test signal"""
        logger.info("🧪 Generating test signal...")
        
        test_signal = {
            'symbol': 'USDJPY',
            'direction': 'CALL',
            'confidence': 72.5,
            'price': 145.23,
            'indicators': ['MA Bullish Crossover', 'RSI Oversold', 'MACD Bullish'],
            'score': 45,
            'timestamp': datetime.now()
        }
        
        signal_id = self.telegram.send_signal(test_signal, Config.SIGNAL_TIMES)
        
        if signal_id:
            logger.info("✅ Test signal sent successfully")
        else:
            logger.error("❌ Failed to send test signal")
        
        return signal_id

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("\n⚠️ Received shutdown signal...")
    if bot:
        bot.stop()
    logger.info("👋 Goodbye!")
    sys.exit(0)

# Global bot instance
bot = None

def main():
    """Main entry point"""
    global bot
    
    try:
        # Create bot instance
        bot = SignalBot()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the bot
        bot.start()
        
        # Keep the main thread alive
        logger.info("Bot is running. Press Ctrl+C to stop.")
        logger.info(f"📌 Invite Link: {Config.INVITE_LINK}")
        logger.info("💡 Share this link with people you want to join!")
        
        # Keep thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user")
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
