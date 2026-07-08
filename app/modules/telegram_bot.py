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
        self.pending_signals = {}  # Track signals waiting for results
        logger.info("Telegram Bot initialized")
        
        # Auto-add admin user on startup
        self._add_admin_user()
    
    def _add_admin_user(self):
        """Auto-add admin user to database"""
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
                logger.info("✅ Admin user 'Bilal' (qSombre) added to database")
            else:
                logger.info("✅ Admin user 'Bilal' already exists in database")
                
        except Exception as e:
            logger.error(f"❌ Failed to add admin user: {e}")
    
    def get_main_menu_keyboard(self):
        """Create the main command keyboard (bottom left)"""
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
        
        # If user is admin, auto-join them
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
                    f"You have been automatically added as an administrator.\n\n"
                    f"📊 **Commands Menu** (tap any button below):\n"
                    f"/invite - Generate invite links\n"
                    f"/status - Check status\n"
                    f"/stats - View statistics\n"
                    f"/signals - Last 5 signals\n"
                    f"/help - Show all commands\n\n"
                    f"🔗 Share this bot with friends using /invite",
                    parse_mode='Markdown',
                    reply_markup=self.get_main_menu_keyboard()
                )
                return
            else:
                await update.message.reply_text(
                    f"👋 Welcome back Admin {first_name}!\n\n"
                    "You're already a member.\n"
                    "Tap a button below to get started.",
                    reply_markup=self.get_main_menu_keyboard()
                )
                return
        
        if existing_user and existing_user['is_active']:
            await update.message.reply_text(
                f"👋 Welcome back {first_name}!\n\n"
                "You're already a member.\n"
                "Tap a button below to get started.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        # Check for invite code
        if context.args and context.args[0].startswith('invite_'):
            invite_code = context.args[0].replace('invite_', '')
            success, message = self.db.add_user_with_invite(
                username=username,
                telegram_id=str(user_id),
                first_name=first_name,
                invite_code=invite_code
            )
            
            if success:
                welcome = f"""
{message}

📊 **Commands Menu** (tap any button below):
/status - Check status
/stats - View statistics
/signals - Last 5 signals
/invite - Get invite link
/help - Show all commands

⚠️ Risk Warning: Trading involves risk!
"""
                await update.message.reply_text(
                    welcome,
                    parse_mode='Markdown',
                    reply_markup=self.get_main_menu_keyboard()
                )
                return
            else:
                await update.message.reply_text(f"❌ {message}")
                return
        
        await update.message.reply_text(
            f"👋 Welcome {first_name}!\n\n"
            "This is a private signal bot.\n"
            "You need an invite link to join.\n\n"
            "Contact the bot administrator for access.",
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def invite_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user = self.db.get_user_by_telegram_id(str(user_id))
        
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You need to be a member to generate invite links.\n"
                "Use a valid invite link to join first.",
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
                await update.message.reply_text(
                    "❌ Error getting bot info. Please try again.",
                    reply_markup=self.get_main_menu_keyboard()
                )
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
            
            # Also show the main menu after
            await update.message.reply_text(
                "📊 **Main Menu**",
                reply_markup=self.get_main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=self.get_main_menu_keyboard()
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You're not a member. Use an invite link to join.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        self.db.update_user_activity(user_id)
        stats = self.db.get_statistics()
        users = self.db.get_user_count()
        
        # Check if user is admin
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
        await update.message.reply_text(
            status_message,
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You're not a member.",
                reply_markup=self.get_main_menu_keyboard()
            )
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
        await update.message.reply_text(
            stats_message,
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user = self.db.get_user_by_telegram_id(user_id)
        
        if not user or not user['is_active']:
            await update.message.reply_text(
                "❌ You're not a member.",
                reply_markup=self.get_main_menu_keyboard()
            )
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
            await update.message.reply_text(
                "📊 No signals yet.\n\nThe bot is analyzing the markets and will send signals when conditions are right.",
                reply_markup=self.get_main_menu_keyboard()
            )
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
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or f"user_{user_id}"
        first_name = update.effective_user.first_name or "User"
        
        # Auto-join for admin
        if str(user_id) == "1669011045":
            success, message = self.db.add_user_with_invite(
                username=username,
                telegram_id=str(user_id),
                first_name=first_name,
                invite_code=None
            )
            if success:
                await update.message.reply_text(
                    f"👑 {message}\n\n👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}",
                    reply_markup=self.get_main_menu_keyboard()
                )
                return
        
        existing_user = self.db.get_user_by_telegram_id(str(user_id))
        if existing_user and existing_user['is_active']:
            await update.message.reply_text(
                "✅ You're already a member!",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        success, message = self.db.add_user_with_invite(
            username=username,
            telegram_id=str(user_id),
            first_name=first_name,
            invite_code=None
        )
        
        if success:
            await update.message.reply_text(
                f"{message}\n\n👥 Users: {self.db.get_user_count()}/{Config.MAX_USERS}",
                reply_markup=self.get_main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ {message}\n\n💡 You need an invite link. Use /invite",
                reply_markup=self.get_main_menu_keyboard()
            )
    
    async def leave_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        
        # Prevent admin from leaving
        if user_id == "1669011045":
            await update.message.reply_text(
                "❌ You are the admin. You cannot leave the group.\n"
                "If you want to stop the bot, you can stop the service on Railway.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_active = 0 WHERE telegram_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            "✅ You have left the group.",
            reply_markup=self.get_main_menu_keyboard()
        )
    
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

**How Results Work:**
1. Bot sends signal with entry time
2. You place the trade
3. Bot automatically checks result after expiry
4. You receive WIN/LOSS notification

**Signal Format:**
📊 Symbol: USDJPY-OTC
📈 Direction: CALL/PUT
💪 Confidence: 65-75%
💰 Price: 145.23
⏰ Bet Time: 14:33:00

⚠️ **Risk Warning:**
Trading involves risk. Only trade with money you can afford to lose.
"""
        await update.message.reply_text(
            help_message,
            parse_mode='Markdown',
            reply_markup=self.get_main_menu_keyboard()
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Telegram error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again.",
                reply_markup=self.get_main_menu_keyboard()
            )
    
    def start(self):
        """Start the Telegram bot"""
        if self.is_running:
            return
        
        try:
            logger.info("🔄 Starting Telegram bot...")
            
            # Create application
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
            async def get_bot_info():
                bot_info = await self.application.bot.get_me()
                self.bot_username = bot_info.username
                logger.info(f"✅ Bot username: @{self.bot_username}")
            
            # Run in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_bot_info())
            
            # Start polling in a separate thread
            def run_polling():
                try:
                    # Create a new event loop for polling
                    polling_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(polling_loop)
                    
                    # Run the application
                    polling_loop.run_until_complete(
                        self.application.initialize()
                    )
                    polling_loop.run_until_complete(
                        self.application.start()
                    )
                    
                    # Start polling
                    polling_loop.run_until_complete(
                        self.application.updater.start_polling(
                            poll_interval=1.0,
                            timeout=30,
                            allowed_updates=["message", "callback_query"]
                        )
                    )
                    
                    # Keep running
                    polling_loop.run_forever()
                    
                except Exception as e:
                    logger.error(f"❌ Polling error: {e}")
                    logger.info("🔄 Will retry in 30 seconds...")
                    time.sleep(30)
                    run_polling()  # Retry
            
            # Start polling in a thread
            polling_thread = threading.Thread(target=run_polling, daemon=True)
            polling_thread.start()
            
            self.is_running = True
            logger.info("✅ Telegram bot started successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram bot: {e}")
            self.is_running = False
    
    def stop(self):
        if self.application:
            try:
                # Stop the application
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.application.stop())
                loop.run_until_complete(self.application.shutdown())
                loop.close()
            except:
                pass
        self.is_running = False
        logger.info("Telegram bot stopped")
    
    def send_signal(self, signal, signal_times=[3, 5]):
        """Send trading signal and track for results"""
        if not signal or signal['direction'] == 'NEUTRAL':
            return None
        
        try:
            # Get current time in Erbil timezone
            now = Config.get_current_time()
            indicators_text = "\n".join([f"• {ind}" for ind in signal.get('indicators', [])])
            
            # Save signal to database first
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
            logger.info(f"💾 Signal saved with ID: {signal_id}")
            
            # Store for result tracking
            self.pending_signals[signal_id] = {
                'symbol': signal['symbol'],
                'direction': signal['direction'],
                'entry_price': signal['price'],
                'bet_time': now + timedelta(minutes=signal_times[0]),
                'expiry_time': now + timedelta(minutes=signal_times[0] + 2),
                'signal_id': signal_id
            }
            
            # Send both alerts (3 min and 5 min)
            async def send_messages():
                for minutes in signal_times:
                    bet_time = now + timedelta(minutes=minutes)
                    bet_time_str = bet_time.strftime("%H:%M:%S")
                    expiry_time = (bet_time + timedelta(minutes=2)).strftime("%H:%M:%S")
                    
                    message = f"""
🎯 **Signal Alert!** ({minutes} min)
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

📌 **ID:** `{signal_id}` (for tracking)
"""
                    
                    await self.application.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    logger.info(f"✅ Signal sent: {signal['symbol']} - {signal['direction']} ({minutes} min)")
            
            # Run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_messages())
            loop.close()
            
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
                
                # Check if signal has expired
                if now >= expiry_time:
                    expired_signals.append(signal_id)
                    
                    # Generate random result (FOR TESTING ONLY)
                    # In production, you would get real data from MT5
                    import random
                    result = random.choice(['WIN', 'LOSS'])
                    profit = round(random.uniform(5.0, 25.0), 2) if result == 'WIN' else -round(random.uniform(5.0, 20.0), 2)
                    
                    # Update database
                    self.db.update_signal_result(signal_id, result, profit)
                    
                    # Send result message
                    result_emoji = "✅" if result == "WIN" else "❌"
                    profit_str = f"+${profit:.2f}" if profit > 0 else f"-${abs(profit):.2f}"
                    
                    result_message = f"""
📊 **Trade Result**
━━━━━━━━━━━━━━━━━━
📌 **ID:** `{signal_id}`
📊 **Symbol:** {signal_data['symbol']}-OTC
📈 **Direction:** {signal_data['direction']}
💰 **Entry:** {signal_data['entry_price']:.4f}
{result_emoji} **Result:** {result}
💵 **Profit:** {profit_str}

⏰ **Time:** {now.strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━━━
#Result #{signal_data['symbol']} #{result}
"""
                    
                    # Send result to Telegram
                    async def send_result():
                        await self.application.bot.send_message(
                            chat_id=self.chat_id,
                            text=result_message,
                            parse_mode='Markdown'
                        )
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(send_result())
                    loop.close()
                    
                    logger.info(f"📊 Result sent: {signal_data['symbol']} - {result} (${profit:.2f})")
            
            # Remove expired signals
            for signal_id in expired_signals:
                del self.pending_signals[signal_id]
                
        except Exception as e:
            logger.error(f"Error checking results: {e}")
