import asyncio
import time
import threading
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from datetime import datetime, timedelta
import json
from app.utils.logger import logger
from app.config import Config

class TelegramBot:
    def __init__(self, db_manager, signal_generator):
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.db = db_manager
        self.signal_generator = signal_generator
        self.bot = None
        self.application = None
        self.is_running = False
        self.bot_username = None
        self.polling_thread = None
        self.loop = None
        logger.info("Telegram Bot initialized")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        
        if existing_user and existing_user['is_active']:
            await update.message.reply_text(
                f"👋 Welcome back {first_name}!\n\n"
                "You're already a member.\n"
                "Use /status to check your status."
            )
            return
        
        if context.args and context.args[0].startswith('invite_'):
            invite_code = context.args[0].replace('invite_', '')
            success, message = self.db.add_user_with_invite(
                username=username,
                telegram_id=str(user_id),
                first_name=first_name,
                invite_code=invite_code
            )
            
            welcome = f"""
{message}

📊 **Commands:**
/status - Check status
/stats - View statistics
/signals - Last 5 signals
/invite - Get invite link
/help - Show all commands

⚠️ Risk Warning: Trading involves risk!
"""
            await update.message.reply_text(welcome, parse_mode='Markdown')
            return
        
        await update.message.reply_text(
            f"👋 Welcome {first_name}!\n\n"
            "This is a private signal bot.\n"
            "You need an invite link to join.\n\n"
            "Contact the bot administrator for access."
        )
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user_by_telegram_id(str(user_id))
        
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You need to be a member to generate invite links.\n"
                "Use a valid invite link to join first."
            )
            return
        
        import secrets
        import string
        alphabet = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        
        if not self.bot_username:
            try:
                bot_info = await self.bot.get_me()
                self.bot_username = bot_info.username
            except:
                await update.message.reply_text("❌ Error getting bot info. Please try again.")
                return
        
        invite_link, message = self.db.generate_invite_link(self.bot_username, code)
        
        if invite_link:
            keyboard = [
                [InlineKeyboardButton("📤 Share Invite Link", url=invite_link)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔗 **Your Invite Link**\n\n"
                f"`{invite_link}`\n\n"
                f"📌 Each link works for **1 person**.\n"
                f"👥 Current users: {self.db.get_user_count()}/{Config.MAX_USERS}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"❌ {message}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member. Use an invite link to join.")
            return
        
        self.db.update_user_activity(user_id)
        stats = self.db.get_statistics()
        users = self.db.get_user_count()
        
        status_message = f"""
📊 **Bot Status**
━━━━━━━━━━━━━━━━━━
👤 **User:** {user['first_name']}
📅 **Joined:** {user['joined_at'][:10]}

📈 **Performance (Last 7 days):**
• Total Signals: {stats['total_signals']}
• Wins: {stats['wins']}
• Losses: {stats['losses']}
• Win Rate: {stats['win_rate']:.1f}%
• Total Profit: ${stats['total_profit']:.2f}

👥 **Group Stats:**
• Active Users: {users}/{Config.MAX_USERS}

📌 **Commands:**
/invite - Generate invite link
/status - Check status
/stats - View statistics
/signals - Last 5 signals
/help - Show all commands
"""
        await update.message.reply_text(status_message, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.")
            return
        
        stats = self.db.get_statistics()
        top_symbols = self.db.get_top_symbols(3)
        
        stats_message = f"""
📈 **Performance Statistics**
━━━━━━━━━━━━━━━━━━
📊 **Last 7 Days:**
• Total Signals: {stats['total_signals']}
• ✅ Wins: {stats['wins']}
• ❌ Losses: {stats['losses']}
• 🏆 Win Rate: {stats['win_rate']:.1f}%
• 💰 Total Profit: ${stats['total_profit']:.2f}

🏆 **Top Symbols:**
"""
        for i, symbol in enumerate(top_symbols, 1):
            stats_message += f"{i}. {symbol['symbol']}: {symbol['win_rate']:.1f}% ({symbol['wins']}/{symbol['total']})\n"
        
        stats_message += f"""
⚡ **Today:**
• Signals: {self.db.get_today_signals()}
• Profit: ${self.db.get_today_profit():.2f}
"""
        await update.message.reply_text(stats_message, parse_mode='Markdown')
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.")
            return
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT symbol, direction, entry_price, result, profit_loss, created_at
            FROM signals ORDER BY created_at DESC LIMIT 5
        ''')
        signals = cursor.fetchall()
        conn.close()
        
        if not signals:
            await update.message.reply_text("📊 No signals yet.")
            return
        
        message = "📊 **Recent Signals**\n━━━━━━━━━━━━━━━━\n"
        for i, signal in enumerate(signals, 1):
            symbol, direction, price, result, profit, time_str = signal
            result_emoji = "✅ WIN" if result == "WIN" else "❌ LOSS" if result == "LOSS" else "⏳ Pending"
            profit_str = f"+${profit:.2f}" if profit and profit > 0 else f"-${abs(profit):.2f}" if profit else "$0.00"
            
            message += f"""
**{i}. {symbol}**
Direction: {direction}
Price: {price:.4f}
Result: {result_emoji}
Profit: {profit_str}
Time: {time_str[:16]}
"""
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        if existing_user and existing_user['is_active']:
            await update.message.reply_text("✅ You're already a member!")
            return
        
        success, message = self.db.add_user_with_invite(
            username=username,
            telegram_id=str(user_id),
            first_name=first_name,
            invite_code=None
        )
        
        if success:
            await update.message.reply_text(f"{message}\n\n👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}")
        else:
            await update.message.reply_text(f"❌ {message}\n\n💡 You need an invite link. Use /invite")
    
    async def leave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_active = 0 WHERE telegram_id = ?', (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ You have left the group.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_message = """
🤖 **Sombre Signals Bot - Help**

**Commands:**
/start - Start the bot
/invite - Generate invite link
/join - Join the group
/leave - Leave the group
/status - Check bot status
/stats - View statistics
/signals - Last 5 signals
/help - Show this message

**How to Join:**
1. Get an invite link from a member
2. Click the link or use: /start invite_CODE
3. You're automatically added!

**Signal Format:**
📊 Symbol: USDJPY-OTC
📈 Direction: CALL/PUT
💪 Confidence: 65-75%
💰 Price: 145.23
⏰ Bet Time: 14:33:00

⚠️ **Risk Warning:**
Trading involves risk. Only trade with money you can afford to lose.
"""
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Telegram error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("⚠️ An error occurred. Please try again.")
    
    def start(self):
        if self.is_running:
            return
        
        try:
            logger.info("🔄 Starting Telegram bot...")
            
            # Create event loop in this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Create bot instance
            self.bot = Bot(token=self.token)
            self.application = Application.builder().token(self.token).build()
            
            # Add handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("invite", self.invite_command))
            self.application.add_handler(CommandHandler("join", self.join_command))
            self.application.add_handler(CommandHandler("leave", self.leave_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("signals", self.signals_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_error_handler(self.error_handler)
            
            # Get bot username
            try:
                bot_info = self.loop.run_until_complete(
                    asyncio.wait_for(self.bot.get_me(), timeout=10)
                )
                self.bot_username = bot_info.username
                logger.info(f"✅ Bot username: @{self.bot_username}")
            except Exception as e:
                logger.error(f"❌ Failed to get bot info: {e}")
                return
            
            # Start polling in a separate thread with its own event loop
            def run_polling():
                try:
                    # Create new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    
                    logger.info("🔄 Starting polling...")
                    self.application.run_polling(
                        poll_interval=1.0,
                        timeout=30,
                        allowed_updates=["message", "callback_query"]
                    )
                except Exception as e:
                    logger.error(f"❌ Polling error: {e}")
                    logger.info("🔄 Will retry in 30 seconds...")
                    time.sleep(30)
                    run_polling()  # Retry
            
            self.polling_thread = threading.Thread(target=run_polling, daemon=True)
            self.polling_thread.start()
            
            self.is_running = True
            logger.info("✅ Telegram bot started successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram bot: {e}")
            self.is_running = False
    
    def stop(self):
        if self.application:
            try:
                self.application.stop()
            except:
                pass
        self.is_running = False
        logger.info("Telegram bot stopped")
    
    def send_signal(self, signal, signal_times=[3, 5]):
        if not signal or signal['direction'] == 'NEUTRAL':
            return None
        
        try:
            now = datetime.now()
            bet_times = [now + timedelta(minutes=t) for t in signal_times]
            indicators_text = "\n".join([f"• {ind}" for ind in signal.get('indicators', [])])
            
            for i, bet_time in enumerate(bet_times):
                minutes = signal_times[i]
                bet_time_str = bet_time.strftime("%H:%M:%S")
                expiry_time = (bet_time + timedelta(minutes=2)).strftime("%H:%M:%S")
                
                message = f"""
🎯 **Signal Alert!** ({i+1}/{len(bet_times)})
━━━━━━━━━━━━━━━━━━
📊 **Symbol:** {signal['symbol']}-OTC
📈 **Direction:** {signal['direction']}
💪 **Confidence:** {signal['confidence']:.1f}%
💰 **Price:** {signal['price']:.4f}
⏰ **Bet Time:** {bet_time_str}
⏱️ **Expiry:** {expiry_time}

📋 **Triggers:**
{indicators_text}

🔔 **Action:**
Place **{signal['direction']}** at **{bet_time_str}**
⚠️ Expiry: **{expiry_time}**
"""
                
                # Use the main loop if available, or create a new one
                if self.loop and self.loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self.bot.send_message(
                            chat_id=self.chat_id,
                            text=message,
                            parse_mode='Markdown'
                        ),
                        self.loop
                    )
                    future.result(timeout=30)
                else:
                    # Fallback: create new loop
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(
                        self.bot.send_message(
                            chat_id=self.chat_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                    )
                    new_loop.close()
                
                logger.info(f"Signal sent: {signal['symbol']} - {signal['direction']}")
            
            signal_data = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['price'],
                'signal_time': datetime.now(),
                'bet_time': bet_times[0],
                'expiry_time': bet_times[0] + timedelta(minutes=2),
                'confidence': signal['confidence'],
                'indicators': signal.get('indicators', [])
            }
            
            signal_id = self.db.save_signal(signal_data)
            return signal_id
            
        except Exception as e:
            logger.error(f"Error sending signal: {e}")
            return None
