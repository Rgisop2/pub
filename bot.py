from pyrogram import Client
from config import API_ID, API_HASH, LOG_CHANNEL, BOTS
from plugins.link_changer import link_changer
from plugins.database import db_instances
import asyncio

class Bot(Client):
    # Dictionary to store all bot instances
    instances = {}
    
    def __init__(self, bot_token, db_instance, version="v1"):
        self.version = version
        self.db = db_instance
        self.bot_token = bot_token
        
        super().__init__(
        f"link_changer_bot_{version}",
         api_id=API_ID,
         api_hash=API_HASH,
         bot_token=bot_token,
         plugins=dict(root="plugins"),
         workers=50,
         sleep_threshold=10
        )
        
        # Store this instance in the class dictionary
        Bot.instances[bot_token] = self

      
    async def start(self):
            
        await super().start()
        me = await self.get_me()
        self.username = '@' + me.username
        
        print(f'✅ {self.version} Bot started successfully (Token: {self.bot_token[:6]}...)')
        
        # Process any pending logs first
        from plugins.link_changer import process_pending_logs
        await process_pending_logs(self)
        
        # Set up periodic log processing
        self.log_processing_task = asyncio.create_task(self._process_logs_periodically())
        
        # Resume all active channels on startup for all logged-in IDs
        await self.resume_all_channels()
        
    async def _process_logs_periodically(self):
        """Process pending logs periodically"""
        from plugins.link_changer import process_pending_logs
        while True:
            try:
                await process_pending_logs(self)
            except Exception as e:
                print(f"[{self.version}] Error processing logs: {e}")
            await asyncio.sleep(5)  # Process logs every 5 seconds

    async def resume_all_channels(self):
        """Resume all active channels on bot startup for all logged-in IDs"""
        try:
            # Get all active channels from this bot's database
            channels = await self.db.get_all_active_channels()
            
            # Create a map to track which channels belong to which phone number
            channel_owners = {}
            
            # First, check if channels have owners already set
            for channel in channels:
                channel_id = channel['channel_id']
                owner_phone = await self.db.get_channel_owner(channel_id)
                if owner_phone:
                    channel_owners[channel_id] = owner_phone
            
            # Group channels by user_id to process them efficiently
            channels_by_user = {}
            for channel in channels:
                user_id = channel['user_id']
                if user_id not in channels_by_user:
                    channels_by_user[user_id] = []
                channels_by_user[user_id].append(channel)
            
            # Process each user's channels
            for user_id, user_channels in channels_by_user.items():
                # Get all sessions for this user
                sessions = await self.db.get_all_sessions(user_id)
                
                if not sessions:
                    print(f"[{self.version}] No sessions found for user {user_id}, skipping their channels")
                    continue
                
                # For each channel, determine which phone number should own it
                for channel in user_channels:
                    channel_id = channel['channel_id']
                    base_username = channel['base_username']
                    interval = channel['interval']
                    
                    # Use the stored owner if available, otherwise assign to first session
                    phone_number = channel_owners.get(channel_id)
                    if not phone_number or phone_number not in sessions:
                        phone_number = list(sessions.keys())[0]
                        # Update the channel owner in the database
                        await self.db.update_channel_owner(channel_id, phone_number)
                    
                    # Start the channel rotation with the appropriate phone number
                    success, result = await link_changer.start_channel_rotation(
                        user_id, 
                        channel_id, 
                        base_username, 
                        interval,
                        phone_number,
                        self.version  # Pass the version to identify which bot is handling this channel
                    )
                    
                    if success:
                        print(f"[{self.version}] Resumed channel rotation for {channel_id} by {phone_number}")
                        # Use the log queue system instead of direct message
                        from plugins.link_changer import send_log
                        send_log(f"[{self.version}] 🔄 Resumed channel rotation for {channel_id} by {phone_number}")
                    else:
                        print(f"[{self.version}] Failed to resume channel {channel_id} by {phone_number}: {result}")
                            
        except Exception as e:
            print(f"[{self.version}] Error resuming channels: {e}")

    async def stop(self, *args):
        # Cancel log processing task if it exists
        if hasattr(self, 'log_processing_task'):
            self.log_processing_task.cancel()
            
        await super().stop()
        print('Bot Stopped Bye')

# For backward compatibility when running bot.py directly
if __name__ == "__main__":
    from plugins.database import db
    from config import BOTS
    
    # Use the first bot configuration if available
    if BOTS:
        bot_config = BOTS[0]
        bot_token = bot_config.get("token")
        version = bot_config.get("version", "v1")
        Bot(bot_token=bot_token, db_instance=db, version=version).run()
    else:
        print("No bot configurations found in config. Please check your config file.")
