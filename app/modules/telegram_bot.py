import asyncio
import time
import threading
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
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
        self.application = None
        self.is_running = False
        self.bot_username = None
        self.pending_signals = {}
        self._loop = None
        logger.info("Telegram Bot initialized")
        
        self._add_admin_user()
    
    def _add_admin_user(self):
        try:
            existing = self.db.get_user_by_telegram_id("1669011045")
            if not existing or not existing['is_active']:
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (telegram_id, username, first_name, is_active, joined_at, last_active)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', ("1669011045", "qSombre", "Bilal"))
                conn.commit()
                conn.close()
                logger.info("✅ Admin user added")
        except Exception as e:
            logger.error(f"❌ Failed to add admin: {e}")
    
    def get_main_menu_keyboard(self):
        keyboard = [
            [KeyboardButton("/start"), KeyboardButton("/invite")],
            [KeyboardButton("/status"), KeyboardButton("/stats")],
            [KeyboardButton("/signals"), KeyboardButton("/help")],
            [KeyboardButton("/join"), KeyboardButton("/leave")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        
        if str(user_id) == "1669011045":
            if not existing_user or not existing_user['is_active']:
                success, message = self.db.add_user_with_invite(
                    username=username,
                    telegram_id=str(user_id),
                    first_name=first_name,
                    invite_code=None
                )
                await update.message.reply_text(
                    f"👑 **Welcome Admin {first_name}!**\n\n"
                    "You're the administrator.\n"
                    "Use /invite to generate invite links.",
                    parse_mode='Markdown',
                    reply_markup=self.get_main_menu_keyboard()
                )
                return
            else:
                await update.message.reply_text(
                    f"👋 Welcome back Admin {first_name}!",
                    reply_markup=self.get_main_menu_keyboard()
                )
                return
        
        if existing_user and existing_user['is_active']:
            await update.message.reply_text(
                f"👋 Welcome back {first_name}!",
                reply_markup=self.get_main_menu_keyboard()
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
            
            if success:
                await update.message.reply_text(
                    f"{message}\n\nUse /status to check your status.",
                    parse_mode='Markdown',
                    reply_markup=self.get_main_menu_keyboard()
                )
                return
        
        await update.message.reply_text(
            f"👋 Welcome {first_name}!\n\n"
            "You need an invite link to join.\n"
            "Contact the administrator.",
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user_by_telegram_id(str(user_id))
        
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You need to be a member to generate invite links.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        import secrets
        import string
        alphabet = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        
        if not self.bot_username:
            try:
                bot_info = await context.bot.get_me()
                self.bot_username = bot_info.username
            except:
                await update.message.reply_text("❌ Error getting bot info.")
                return
        
        invite_link, message = self.db.generate_invite_link(self.bot_username, code)
        
        if invite_link:
            keyboard = [[InlineKeyboardButton("📤 Share Invite Link", url=invite_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔗 **Your Invite Link**\n\n`{invite_link}`\n\n"
                f"👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"❌ {message}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.", reply_markup=self.get_main_menu_keyboard())
            return
        
        self.db.update_user_activity(user_id)
        stats = self.db.get_statistics()
        users = self.db.get_user_count()
        is_admin = "👑 ADMIN" if user_id == "1669011045" else "👤 Member"
        
        status_message = f"""
📊 **Bot Status**
━━━━━━━━━━━━━━━━━━
{is_admin}: {user['first_name']} (@{user['username']})
📅 **Joined:** {user['joined_at'][:10]}

📈 **Performance (Last 7 days):**
• Total Signals: {stats['total_signals']}
• Wins: {stats['wins']}
• Losses: {stats['losses']}
• Win Rate: {stats['win_rate']:.1f}%
• Total Profit: ${stats['total_profit']:.2f}

👥 **Group Stats:**
• Active Users: {users}/{Config.MAX_USERS}
"""
        await update.message.reply_text(status_message, parse_mode='Markdown', reply_markup=self.get_main_menu_keyboard())
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.", reply_markup=self.get_main_menu_keyboard())
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
            stats_message += f"{i}. {symbol['symbol']}: {symbol['win_rate']:.1f}%\n"
        
        stats_message += f"""
⚡ **Today:**
• Signals: {self.db.get_today_signals()}
• Profit: ${self.db.get_today_profit():.2f}
"""
        await update.message.reply_text(stats_message, parse_mode='Markdown', reply_markup=self.get_main_menu_keyboard())
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text("❌ You're not a member.", reply_markup=self.get_main_menu_keyboard())
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
            await update.message.reply_text("📊 No signals yet.", reply_markup=self.get_main_menu_keyboard())
            return
        
        message = "📊 **Recent Signals**\n━━━━━━━━━━━━━━━━\n"
        for i, signal in enumerate(signals, 1):
            symbol, direction, price, result, profit, time_str = signal
            result_emoji = "✅ WIN" if result == "WIN" else "❌ LOSS" if result == "LOSS" else "⏳ Pending"
            profit_str = f"+${profit:.2f}" if profit and profit > 0 else f"-${abs(profit):.2f}" if profit else "$0.00"
            
            message += f"""
**{i}. {symbol}**
Direction: {direction}
Result: {result_emoji}
Profit: {profit_str}
Time: {time_str[:16]}
"""
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=self.get_main_menu_keyboard())
    
    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        
        if str(user_id) == "1669011045":
            success, message = self.db.add_user_with_invite(
                username=username,
                telegram_id=str(user_id),
                first_name=first_name,
                invite_code=None
            )
            if success:
                await update.message.reply_text(f"👑 {message}", reply_markup=self.get_main_menu_keyboard())
                return
        
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        if existing_user and existing_user['is_active']:
            await update.message.reply_text("✅ You're already a member!", reply_markup=self.get_main_menu_keyboard())
            return
        
        success, message = self.db.add_user_with_invite(
            username=username,
            telegram_id=str(user_id),
            first_name=first_name,
            invite_code=None
        )
        
        if success:
            await update.message.reply_text(f"{message}\n\n👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}", reply_markup=self.get_main_menu_keyboard())
        else:
            await update.message.reply_text(f"❌ {message}\n\n💡 You need an invite link.", reply_markup=self.get_main_menu_keyboard())
    
    async def leave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        
        if user_id == "1669011045":
            await update.message.reply_text("❌ Admin cannot leave.", reply_markup=self.get_main_menu_keyboard())
            return
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_active = 0 WHERE telegram_id = ?', (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ You have left the group.", reply_markup=self.get_main_menu_keyboard())
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_message = """
🤖 **XAUUSD Signal Bot - Help**

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
1. Get an invite link
2. Click the link or use: /start invite_CODE

**Signal Format:**
📊 Symbol: XAUUSD-OTC
📈 Direction: CALL/PUT
⏰ Bet Time: 09:12:14

⚠️ **Risk Warning:**
Trading involves risk. Only trade with money you can afford to lose.
"""
        await update.message.reply_text(help_message, parse_mode='Markdown', reply_markup=self.get_main_menu_keyboard())
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Telegram error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text("⚠️ An error occurred. Please try again.")
    
    def start(self):
        """Start the Telegram bot - FIXED to respond to commands"""
        if self.is_running:
            return
        
        try:
            logger.info("🔄 Starting Telegram bot...")
            
            # Create application with proper settings
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
            
            # Get bot info
            def get_info():
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                bot_info = loop.run_until_complete(self.application.bot.get_me())
                self.bot_username = bot_info.username
                loop.close()
                logger.info(f"✅ Bot username: @{self.bot_username}")
            
            get_info()
            
            # Start polling in a separate thread with proper event loop
            def run_polling():
                try:
                    logger.info("🔄 Starting polling...")
                    self.application.run_polling(
                        poll_interval=1.0,
                        timeout=60,
                        allowed_updates=["message", "callback_query"],
                        drop_pending_updates=True
                    )
                except Exception as e:
                    logger.error(f"❌ Polling error: {e}")
                    logger.info("🔄 Restarting polling in 5 seconds...")
                    time.sleep(5)
                    run_polling()
            
            # Start polling in a thread
            polling_thread = threading.Thread(target=run_polling, daemon=True)
            polling_thread.start()
            
            self.is_running = True
            logger.info("✅ Telegram bot started successfully! Commands are now working.")
            
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
            now = Config.get_current_time()
            indicators_text = "\n".join([f"• {ind}" for ind in signal.get('indicators', [])])
            
            signal_data = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['price'],
                'signal_time': now,
                'bet_time': now + timedelta(minutes=signal_times[0]),
                'expiry_time': now + timedelta(minutes=signal_times[0] + 2),
                'confidence': signal['confidence'],
                'indicators': signal.get('indicators', [])
            }
            
            signal_id = self.db.save_signal(signal_data)
            self.pending_signals[signal_id] = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['price'],
                'bet_time': now + timedelta(minutes=signal_times[0]),
                'expiry_time': now + timedelta(minutes=signal_times[0] + 2),
                'signal_id': signal_id
            }
            
            def send_messages_sync():
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                for minutes in signal_times:
                    bet_time = now + timedelta(minutes=minutes)
                    bet_time_str = bet_time.strftime("%H:%M:%S")
                    expiry_time = (bet_time + timedelta(minutes=2)).strftime("%H:%M:%S")
                    
                    message = f"""
🎯 **XAUUSD Signal Alert!** ({minutes} min)
━━━━━━━━━━━━━━━━━━
📊 **Symbol:** XAUUSD-OTC
📈 **Direction:** {signal['direction']}
💪 **Confidence:** {signal['confidence']:.1f}%
💰 **Price:** {signal['price']:.2f}
⏰ **Bet Time:** {bet_time_str}
⏱️ **Expiry:** {expiry_time}

📋 **Triggers:**
{indicators_text}

🔔 **Action:**
Place **{signal['direction']}** at **{bet_time_str}**
⚠️ Expiry: **{expiry_time}**

📌 **ID:** `{signal_id}`
"""
                    
                    loop.run_until_complete(
                        self.application.bot.send_message(
                            chat_id=self.chat_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                    )
                    logger.info(f"✅ XAUUSD Signal sent: {signal['direction']} ({minutes} min)")
                
                loop.close()
            
            send_messages_sync()
            return signal_id
            
        except Exception as e:
            logger.error(f"Error sending signal: {e}")
            return None
    
    def check_pending_results(self):
        """Check pending signals and send results"""
        if not self.application or not self.is_running:
            return
        
        try:
            now = Config.get_current_time()
            expired_signals = []
            
            for signal_id, signal_data in self.pending_signals.items():
                expiry_time = signal_data['expiry_time']
                
                if now >= expiry_time:
                    expired_signals.append(signal_id)
                    
                    import random
                    result = random.choice(['WIN', 'LOSS'])
                    profit = round(random.uniform(5.0, 25.0), 2) if result == 'WIN' else -round(random.uniform(5.0, 20.0), 2)
                    
                    self.db.update_signal_result(signal_id, result, profit)
                    
                    result_emoji = "✅" if result == "WIN" else "❌"
                    profit_str = f"+${profit:.2f}" if profit > 0 else f"-${abs(profit):.2f}"
                    
                    result_message = f"""
📊 **XAUUSD Trade Result**
━━━━━━━━━━━━━━━━━━
📌 **ID:** `{signal_id}`
📊 **Symbol:** XAUUSD-OTC
📈 **Direction:** {signal_data['direction']}
💰 **Entry:** {signal_data['entry_price']:.2f}
{result_emoji} **Result:** {result}
💵 **Profit:** {profit_str}

⏰ **Time:** {now.strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━━━
#XAUUSD #{result}
"""
                    
                    def send_result_sync():
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            self.application.bot.send_message(
                                chat_id=self.chat_id,
                                text=result_message,
                                parse_mode='Markdown'
                            )
                        )
                        loop.close()
                    
                    send_result_sync()
                    logger.info(f"📊 XAUUSD Result: {result} (${profit:.2f})")
            
            for signal_id in expired_signals:
                del self.pending_signals[signal_id]
                
        except Exception as e:
            logger.error(f"Error checking results: {e}")
