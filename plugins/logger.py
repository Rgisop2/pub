# Telegram Logging System
from config import LOG_CHANNEL
from pyrogram import Client
from datetime import datetime

class Logger:
    def __init__(self):
        self.bot = None
    
    def set_bot(self, bot: Client):
        """Set the bot client for sending logs"""
        self.bot = bot
    
    async def log(self, message: str, emoji: str = "ℹ️"):
        """Send a log message to LOG_CHANNEL"""
        if not self.bot or not LOG_CHANNEL:
            print(f"[v0] {emoji} {message}")
            return
        
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[v0] {emoji} {message}\n`{timestamp}`"
            await self.bot.send_message(LOG_CHANNEL, formatted_message)
        except Exception as e:
            print(f"[v0] Failed to send log: {e}")
            print(f"[v0] {emoji} {message}")
    
    async def success(self, message: str):
        """Log a success message"""
        await self.log(message, "✅")
    
    async def error(self, message: str):
        """Log an error message"""
        await self.log(message, "⚠️")
    
    async def info(self, message: str):
        """Log an info message"""
        await self.log(message, "ℹ️")
    
    async def link_changed(self, channel_id: int, new_username: str):
        """Log successful link change"""
        await self.success(f"Link changed for channel {channel_id}:\nNew username → {new_username}")
    
    async def link_change_failed(self, channel_id: int, error: str):
        """Log failed link change"""
        await self.error(f"Failed to change link for channel {channel_id}:\nReason → {error}")
    
    async def channel_added(self, channel_id: int, phone_number: str):
        """Log channel addition"""
        await self.info(f"🧾 New channel added for auto rotation: {channel_id}\nAccount: {phone_number}")
    
    async def channel_removed(self, channel_id: int):
        """Log channel removal"""
        await self.info(f"🗑️ Channel removed from auto rotation: {channel_id}")
    
    async def channel_paused(self, channel_id: int):
        """Log channel pause"""
        await self.info(f"💤 Link change paused for channel {channel_id}")
    
    async def channel_resumed(self, channel_id: int):
        """Log channel resume"""
        await self.info(f"🔄 Link change resumed for channel {channel_id}")
    
    async def user_login(self, phone_number: str):
        """Log user login"""
        await self.success(f"User {phone_number} logged in successfully")
    
    async def user_logout(self, phone_number: str):
        """Log user logout"""
        await self.info(f"👋 User {phone_number} logged out")
    
    async def bot_started(self):
        """Log bot startup"""
        await self.info(f"🤖 Bot started and resuming all channels...")
    
    async def bot_stopped(self):
        """Log bot shutdown"""
        await self.info(f"🛑 Bot stopped")

logger = Logger()
